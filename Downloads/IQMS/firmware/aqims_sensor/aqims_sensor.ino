// ============================================================
//  AQIMS — Firmware ESP32 Thing Plus
//  Carte : ENUMA Air Quality Monitor (Mai 2024)
//
//  Capteurs (brochage PCB IMG_3178) :
//    GPIO17 (A0)  — DHT22     : Température + Humidité  (R2 10kΩ)
//    GPIO18 (A1)  — LDR       : Luminosité ADC          (R4 10kΩ)
//    GPIO19 (A2)  — MQ7       : CO / Qualité air ADC    (R3 470Ω + R5 1kΩ, VBUS)
//    GPIO23 (SCK) — DS18B20   : Température 1-Wire      (R1 4.7kΩ)
//
//  Communication : MQTT + TLS 1.3 + Certificats mutuels + QoS=2
//  FOTA : mise à jour firmware via HTTPS signé HMAC-SHA256
// ============================================================

#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <WiFiManager.h>          // https://github.com/tzapu/WiFiManager
#include <Preferences.h>          // NVS — stockage persistant ESP32
#include <PubSubClient.h>
#include <DHT.h>
#include <OneWire.h>
#include <DallasTemperature.h>
#include <ArduinoJson.h>
#include <HTTPUpdate.h>
#include <mbedtls/md.h>
#include <time.h>

#include "config.h"
#include "certs.h"   // Généré par scripts/generate_certs.py

// ── Stockage NVS (WiFiManager sauve le WiFi, on sauve le reste) ─
Preferences prefs;

// ── OneWire / DS18B20 ────────────────────────────────────────
OneWire           oneWire(PIN_DS18B20);
DallasTemperature ds18b20(&oneWire);

// ── DHT22 ────────────────────────────────────────────────────
DHT dht(PIN_DHT22, DHT22);

// ── MQTT / TLS ───────────────────────────────────────────────
WiFiClientSecure  wifiClient;
PubSubClient      mqttClient(wifiClient);

// ── Config MQTT lue depuis NVS (configurable via portail WiFiManager) ──
char cfg_mqtt_host[64];
char cfg_mqtt_port[6];
char cfg_mqtt_user[32];
char cfg_mqtt_pass[64];
char cfg_device_id[32];
char cfg_location[32];

// ── Topics MQTT construits au runtime depuis cfg_device_id ───
char topic_sensors[64];
char topic_status[64];
char topic_ota[64];
char topic_config[64];

// ── Cache scan WiFi (géolocalisation) ────────────────────────
struct WifiAP {
  char bssid[18];   // "AA:BB:CC:DD:EE:FF"
  int  rssi;
};
static WifiAP     cachedAPs[5];
static int        cachedAPCount  = 0;
static unsigned long lastWifiScan = 0;

// ── Variables d'état ─────────────────────────────────────────
unsigned long lastSensorRead = 0;
unsigned long lastStatusSend = 0;
unsigned long lastOtaCheck   = 0;
bool          otaRequested   = false;
String        otaUrl         = "";

// ── Structure données capteurs ────────────────────────────────
struct SensorData {
  // DHT22
  float temperature_dht = NAN;   // °C
  float humidity        = NAN;   // %

  // DS18B20
  float temperature_ds  = NAN;   // °C (numérique, plus précis)

  // LDR
  int   ldr_raw         = 0;     // 0-4095 (12 bits ADC)
  float lux             = 0.0;   // valeur estimée

  // MQ7
  int   mq7_raw         = 0;     // 0-4095
  float co_ppm          = 0.0;   // ppm CO estimé

  // Indice qualité
  int   aqi             = 0;
};

SensorData sensors;


// ============================================================
//  SETUP
// ============================================================
void setup() {
  Serial.begin(115200);
  delay(500);
  Serial.println("\n== AQIMS Firmware v" FIRMWARE_VERSION " ==");
  Serial.println("Carte : ENUMA Air Quality Monitor");

  // Init capteurs
  dht.begin();
  ds18b20.begin();
  pinMode(PIN_LDR, INPUT);
  pinMode(PIN_MQ7, INPUT);

  // Bouton RESET WiFi (GPIO0 = BOOT)
  pinMode(WIFI_RESET_PIN, INPUT_PULLUP);

  // Connexion WiFi via WiFiManager (portail si nécessaire)
  connectWiFi();
  syncNTP();
  scanWiFiNetworks();   // première géolocalisation dès le boot
  setupMQTT();

  Serial.println("== Demarrage capteurs ==");
  Serial.printf("  DHT22    : GPIO%d\n", PIN_DHT22);
  Serial.printf("  LDR      : GPIO%d (ADC)\n", PIN_LDR);
  Serial.printf("  MQ7      : GPIO%d (ADC)\n", PIN_MQ7);
  Serial.printf("  DS18B20  : GPIO%d (1-Wire)\n", PIN_DS18B20);
}


// ============================================================
//  LOOP
// ============================================================
void loop() {
  if (!mqttClient.connected()) {
    reconnectMQTT();
  }
  mqttClient.loop();

  unsigned long now = millis();

  if (now - lastSensorRead >= SENSOR_INTERVAL_MS) {
    lastSensorRead = now;
    readAllSensors();
    publishSensorData();
    checkAlertThresholds();
  }

  if (now - lastStatusSend >= STATUS_INTERVAL_MS) {
    lastStatusSend = now;
    publishDeviceStatus();
  }

  if (now - lastWifiScan >= WIFI_SCAN_INTERVAL_MS) {
    lastWifiScan = now;
    scanWiFiNetworks();
  }

  if (now - lastOtaCheck >= OTA_CHECK_INTERVAL_MS) {
    lastOtaCheck = now;
    checkForUpdate();
  }

  if (otaRequested && otaUrl.length() > 0) {
    performOTAUpdate(otaUrl);
    otaRequested = false;
    otaUrl = "";
  }
}


// ============================================================
//  WIFI — WiFiManager (portail de configuration)
// ============================================================
void connectWiFi() {
  // ── ID auto depuis MAC (disponible dès que le mode WiFi est actif) ──
  WiFi.mode(WIFI_STA);
  String mac = WiFi.macAddress();   // "A4:CF:12:AB:CD:EF"
  mac.replace(":", "");
  mac.toLowerCase();
  String autoId = "esp32-" + mac;   // "esp32-a4cf12abcdef" — unique par puce

  // ── Vérifier si le bouton BOOT est maintenu → reset WiFi ──
  if (digitalRead(WIFI_RESET_PIN) == LOW) {
    Serial.println("Bouton BOOT detecte — attente 3s pour reset WiFi...");
    delay(3000);
    if (digitalRead(WIFI_RESET_PIN) == LOW) {
      Serial.println("Reset WiFi confirme ! Suppression des credentials...");
      WiFiManager wm;
      wm.resetSettings();
      Serial.println("Redemarrage...");
      delay(1000);
      ESP.restart();
    }
  }

  // ── Charger la config MQTT sauvegardée en NVS ─────────────
  // autoId (MAC) est utilisé comme valeur par défaut si l'appareil
  // n'a jamais été configuré → garantit l'unicité sans aucune action manuelle.
  prefs.begin("aqims", false);
  strncpy(cfg_mqtt_host, prefs.getString("mqtt_host", MQTT_HOST).c_str(),       sizeof(cfg_mqtt_host));
  strncpy(cfg_mqtt_port, prefs.getString("mqtt_port", "8883").c_str(),          sizeof(cfg_mqtt_port));
  strncpy(cfg_mqtt_user, prefs.getString("mqtt_user", MQTT_USERNAME).c_str(),   sizeof(cfg_mqtt_user));
  strncpy(cfg_mqtt_pass, prefs.getString("mqtt_pass", MQTT_PASSWORD).c_str(),   sizeof(cfg_mqtt_pass));
  strncpy(cfg_device_id, prefs.getString("device_id", autoId).c_str(),          sizeof(cfg_device_id));
  strncpy(cfg_location,  prefs.getString("location",  "inconnu").c_str(),        sizeof(cfg_location));
  prefs.end();

  // ── Paramètres personnalisés dans le portail WiFiManager ──
  WiFiManagerParameter p_mqtt_host("mqtt_host", "Serveur MQTT",    cfg_mqtt_host, 64);
  WiFiManagerParameter p_mqtt_port("mqtt_port", "Port MQTT (TLS)", cfg_mqtt_port, 6);
  WiFiManagerParameter p_mqtt_user("mqtt_user", "Utilisateur MQTT",cfg_mqtt_user, 32);
  WiFiManagerParameter p_mqtt_pass("mqtt_pass", "Mot de passe MQTT",cfg_mqtt_pass,64);
  WiFiManagerParameter p_device_id("device_id", "ID Appareil",     cfg_device_id, 32);
  WiFiManagerParameter p_location ("location",  "Emplacement",     cfg_location,  32);

  WiFiManager wm;
  wm.addParameter(&p_mqtt_host);
  wm.addParameter(&p_mqtt_port);
  wm.addParameter(&p_mqtt_user);
  wm.addParameter(&p_mqtt_pass);
  wm.addParameter(&p_device_id);
  wm.addParameter(&p_location);

  wm.setConfigPortalTimeout(WIFI_TIMEOUT_S);
  wm.setConnectTimeout(20);
  // Message d'info dans le portail
  wm.setCustomHeadElement("<h3 style='color:#0891b2'>AQIMS — Capteur air</h3>");

  Serial.println("WiFiManager : tentative de connexion automatique...");

  // autoConnect : se connecte si credentials connus, sinon ouvre le portail AP
  bool connected = wm.autoConnect(WIFI_AP_NAME, WIFI_AP_PASSWORD);

  if (!connected) {
    Serial.println("Portail ferme sans connexion — redemarrage");
    delay(1000);
    ESP.restart();
  }

  Serial.printf("WiFi OK — IP : %s  SSID : %s\n",
    WiFi.localIP().toString().c_str(), WiFi.SSID().c_str());

  // ── Sauvegarder les paramètres MQTT si modifiés ────────────
  strncpy(cfg_mqtt_host, p_mqtt_host.getValue(), sizeof(cfg_mqtt_host));
  strncpy(cfg_mqtt_port, p_mqtt_port.getValue(), sizeof(cfg_mqtt_port));
  strncpy(cfg_mqtt_user, p_mqtt_user.getValue(), sizeof(cfg_mqtt_user));
  strncpy(cfg_mqtt_pass, p_mqtt_pass.getValue(), sizeof(cfg_mqtt_pass));
  strncpy(cfg_device_id, p_device_id.getValue(), sizeof(cfg_device_id));
  strncpy(cfg_location,  p_location.getValue(),  sizeof(cfg_location));

  prefs.begin("aqims", false);
  prefs.putString("mqtt_host", cfg_mqtt_host);
  prefs.putString("mqtt_port", cfg_mqtt_port);
  prefs.putString("mqtt_user", cfg_mqtt_user);
  prefs.putString("mqtt_pass", cfg_mqtt_pass);
  prefs.putString("device_id", cfg_device_id);
  prefs.putString("location",  cfg_location);
  prefs.end();
  Serial.println("Config MQTT sauvegardee en flash");

  // ── Construire les topics MQTT depuis l'ID définitif ───────
  snprintf(topic_sensors, sizeof(topic_sensors), "aqims/sensors/%s", cfg_device_id);
  snprintf(topic_status,  sizeof(topic_status),  "aqims/status/%s",  cfg_device_id);
  snprintf(topic_ota,     sizeof(topic_ota),     "aqims/ota/%s/update", cfg_device_id);
  snprintf(topic_config,  sizeof(topic_config),  "aqims/config/%s",  cfg_device_id);
  Serial.printf("Device ID : %s\n", cfg_device_id);
  Serial.printf("Topic pub : %s\n", topic_sensors);
}


// ============================================================
//  NTP
// ============================================================
void syncNTP() {
  configTime(0, 0, "pool.ntp.org", "time.nist.gov");
  Serial.print("NTP sync");
  time_t now = time(nullptr);
  int attempts = 0;
  while (now < 8 * 3600 * 2 && attempts < 20) {
    delay(500);
    Serial.print(".");
    now = time(nullptr);
    attempts++;
  }
  Serial.println(" OK");
}


// ============================================================
//  MQTT — Configuration TLS + Connexion
// ============================================================
void setupMQTT() {
  wifiClient.setCACert(CA_CERT);
  wifiClient.setCertificate(CLIENT_CERT);
  wifiClient.setPrivateKey(CLIENT_KEY);

  // Utilise les valeurs lues depuis la flash (configurables via portail WiFiManager)
  int port = atoi(cfg_mqtt_port);
  if (port <= 0) port = MQTT_PORT;

  mqttClient.setServer(cfg_mqtt_host, port);
  mqttClient.setCallback(onMQTTMessage);
  mqttClient.setBufferSize(2048);
  mqttClient.setKeepAlive(60);

  Serial.printf("MQTT -> %s:%d  user=%s\n", cfg_mqtt_host, port, cfg_mqtt_user);
  reconnectMQTT();
}


void reconnectMQTT() {
  int attempts = 0;
  while (!mqttClient.connected() && attempts < 5) {
    Serial.printf("MQTT : connexion [%s]...\n", DEVICE_ID);

    if (mqttClient.connect(cfg_device_id, cfg_mqtt_user, cfg_mqtt_pass)) {
      Serial.println("MQTT OK");
      mqttClient.subscribe(topic_ota,    2);
      mqttClient.subscribe(topic_config, 1);
      publishDeviceStatus();
    } else {
      Serial.printf("MQTT echec (code=%d), retry 5s\n", mqttClient.state());
      delay(5000);
      attempts++;
    }
  }
}


// ============================================================
//  MQTT — Réception
// ============================================================
void onMQTTMessage(char* topic, byte* payload, unsigned int length) {
  String topicStr(topic);
  String msg;
  for (unsigned int i = 0; i < length; i++) msg += (char)payload[i];
  Serial.printf("MQTT [%s] : %s\n", topic, msg.c_str());

  if (topicStr == String(topic_ota)) {
    StaticJsonDocument<512> doc;
    if (deserializeJson(doc, msg) == DeserializationError::Ok) {
      if (doc.containsKey("url") && doc.containsKey("sha256")) {
        otaUrl      = String((const char*)doc["url"]);
        otaRequested = true;
        Serial.printf("OTA demandee : %s\n", otaUrl.c_str());
      }
    }
  }

  if (topicStr == String(topic_config)) {
    Serial.println("Config mise a jour recue");
    // Appliquer seuils / intervalles si besoin
  }
}


// ============================================================
//  CAPTEURS
// ============================================================
void readAllSensors() {
  readDHT22();
  readDS18B20();
  readLDR();
  readMQ7();
  sensors.aqi = calculateAQI(sensors.co_ppm, sensors.ldr_raw);
}


// ── DHT22 : Température + Humidité ───────────────────────────
void readDHT22() {
  float h = dht.readHumidity();
  float t = dht.readTemperature();

  if (isnan(h) || isnan(t)) {
    Serial.println("DHT22 : lecture echouee");
    return;
  }
  sensors.humidity        = h;
  sensors.temperature_dht = t;
  Serial.printf("DHT22  -> Temp: %.1f C  Hum: %.1f%%\n", t, h);
}


// ── DS18B20 : Température numérique 1-Wire ───────────────────
void readDS18B20() {
  ds18b20.requestTemperatures();
  float t = ds18b20.getTempCByIndex(0);

  if (t == DEVICE_DISCONNECTED_C) {
    Serial.println("DS18B20 : capteur non detecte");
    return;
  }
  sensors.temperature_ds = t;
  Serial.printf("DS18B20 -> Temp: %.2f C\n", t);
}


// ── LDR : Luminosité ─────────────────────────────────────────
void readLDR() {
  // ADC 12 bits (0-4095) — diviseur de tension R4 10kΩ / LDR
  // Plus la lumière est forte, plus la tension monte (LDR en bas)
  sensors.ldr_raw = analogRead(PIN_LDR);

  // Conversion approximative en lux (à calibrer selon LDR utilisé)
  // Formule linéaire indicative : 0 = nuit, 4095 = plein soleil ~100 000 lux
  sensors.lux = (sensors.ldr_raw / 4095.0f) * 100000.0f;
  Serial.printf("LDR     -> raw: %d  lux: %.0f\n", sensors.ldr_raw, sensors.lux);
}


// ── MQ7 : CO / Qualité air ───────────────────────────────────
void readMQ7() {
  // MQ7 alimenté en VBUS (5V), sortie analogique sur A2 (GPIO19)
  // R3 470Ω (série) + R5 1kΩ (pull-down) forment un pont de tension
  sensors.mq7_raw = analogRead(PIN_MQ7);

  // Conversion brute → ppm CO (calibration nécessaire sur site)
  // MQ7 : Rs/Ro ratio → courbe logarithmique. Approx. linéaire pour démo.
  // Valeur typique : raw ~800 = air pur (~10 ppm), raw ~3000 = 100+ ppm
  float voltage = (sensors.mq7_raw / 4095.0f) * 3.3f;
  if (voltage < 0.01f) voltage = 0.01f;
  // Approximation : ppm = A * (V / Vref)^B — constantes à calibrer
  sensors.co_ppm = 10.0f * pow((voltage / 3.3f), -1.5f);
  sensors.co_ppm = constrain(sensors.co_ppm, 0, 1000);

  Serial.printf("MQ7     -> raw: %d  CO: %.1f ppm\n", sensors.mq7_raw, sensors.co_ppm);
}


// ============================================================
//  CALCUL AQI simplifié (basé CO + luminosité)
// ============================================================
int calculateAQI(float co_ppm, int ldr_raw) {
  // CO : principal polluant mesuré par MQ7
  // Seuils OMS / EPA pour le CO
  int aqi_co = 0;
  if (co_ppm <= 4.4)        aqi_co = map((int)(co_ppm * 10),  0,  44,   0,  50);
  else if (co_ppm <= 9.4)   aqi_co = map((int)(co_ppm * 10), 45,  94,  51, 100);
  else if (co_ppm <= 12.4)  aqi_co = map((int)(co_ppm * 10), 95, 124, 101, 150);
  else if (co_ppm <= 15.4)  aqi_co = map((int)(co_ppm * 10),125, 154, 151, 200);
  else if (co_ppm <= 30.4)  aqi_co = map((int)(co_ppm * 10),155, 304, 201, 300);
  else                       aqi_co = 301;

  return constrain(aqi_co, 0, 500);
}


// ============================================================
//  SCAN WIFI — Géolocalisation
// ============================================================
void scanWiFiNetworks() {
  Serial.println("Scan WiFi pour geolocalisation...");

  // Scan bloquant, réseaux cachés inclus
  // L'ESP32 reste connecté au réseau courant pendant le scan (station mode)
  int n = WiFi.scanNetworks(false, true);
  cachedAPCount = 0;

  if (n <= 0) {
    Serial.println("Aucun reseau visible");
    WiFi.scanDelete();
    return;
  }

  int limit = min(n, 5);   // 5 APs suffisent pour la géolocalisation MLS
  for (int i = 0; i < limit; i++) {
    strncpy(cachedAPs[cachedAPCount].bssid,
            WiFi.BSSIDstr(i).c_str(),
            sizeof(cachedAPs[cachedAPCount].bssid) - 1);
    cachedAPs[cachedAPCount].rssi = WiFi.RSSI(i);
    Serial.printf("  AP[%d] %s  RSSI: %d dBm\n",
                  i, cachedAPs[cachedAPCount].bssid, cachedAPs[cachedAPCount].rssi);
    cachedAPCount++;
  }

  WiFi.scanDelete();   // libérer la mémoire du scan
  Serial.printf("Scan WiFi OK : %d reseaux en cache\n", cachedAPCount);
}


// ============================================================
//  PUBLICATION MQTT
// ============================================================
void publishSensorData() {
  if (!mqttClient.connected()) return;

  time_t now_t = time(nullptr);
  struct tm* tm_info = gmtime(&now_t);
  char timestamp[30];
  strftime(timestamp, sizeof(timestamp), "%Y-%m-%dT%H:%M:%SZ", tm_info);

  // Température principale : DS18B20 si disponible, sinon DHT22
  float temp_main = !isnan(sensors.temperature_ds)
                    ? sensors.temperature_ds
                    : sensors.temperature_dht;

  StaticJsonDocument<1024> doc;
  doc["device_id"]         = cfg_device_id;
  doc["location"]          = cfg_location;
  doc["timestamp"]         = timestamp;
  doc["firmware"]          = FIRMWARE_VERSION;

  // Données capteurs
  doc["temperature"]       = isnan(temp_main)               ? 0.0f : temp_main;
  doc["temperature_dht"]   = isnan(sensors.temperature_dht) ? 0.0f : sensors.temperature_dht;
  doc["temperature_ds"]    = isnan(sensors.temperature_ds)  ? 0.0f : sensors.temperature_ds;
  doc["humidity"]          = isnan(sensors.humidity)        ? 0.0f : sensors.humidity;
  doc["ldr_raw"]           = sensors.ldr_raw;
  doc["lux"]               = sensors.lux;
  doc["mq7_raw"]           = sensors.mq7_raw;
  doc["co_ppm"]            = sensors.co_ppm;
  doc["aqi"]               = sensors.aqi;

  // Tableau WiFi pour géolocalisation MLS (Mozilla Location Services)
  // Le backend extrait lat/lng via l'API MLS si aucun GPS n'est présent.
  if (cachedAPCount > 0) {
    JsonArray wifiArr = doc.createNestedArray("wifi");
    for (int i = 0; i < cachedAPCount; i++) {
      JsonObject ap = wifiArr.createNestedObject();
      ap["bssid"]  = cachedAPs[i].bssid;
      ap["signal"] = cachedAPs[i].rssi;
    }
  }

  char buffer[1024];
  serializeJson(doc, buffer);

  bool ok = mqttClient.publish(topic_sensors, buffer, false);
  Serial.printf("MQTT pub %s (AQI=%d, %d APs WiFi)\n",
                ok ? "OK" : "ECHEC", sensors.aqi, cachedAPCount);
}


void publishDeviceStatus() {
  if (!mqttClient.connected()) return;

  StaticJsonDocument<256> doc;
  doc["device_id"]  = cfg_device_id;
  doc["status"]     = "online";
  doc["firmware"]   = FIRMWARE_VERSION;
  doc["ip"]         = WiFi.localIP().toString();
  doc["rssi"]       = WiFi.RSSI();
  doc["free_heap"]  = ESP.getFreeHeap();
  doc["uptime_s"]   = millis() / 1000;

  char buffer[256];
  serializeJson(doc, buffer);
  mqttClient.publish(topic_status, buffer, true);   // retain=true
}


void checkAlertThresholds() {
  if (sensors.aqi > 100)
    Serial.printf("ALERTE AQI eleve : %d\n", sensors.aqi);
  if (sensors.co_ppm > 9.0)
    Serial.printf("ALERTE CO eleve : %.1f ppm\n", sensors.co_ppm);
  if (!isnan(sensors.humidity) && sensors.humidity > 80.0)
    Serial.printf("ALERTE Humidite : %.1f%%\n", sensors.humidity);
}


// ============================================================
//  FOTA — Vérification et mise à jour
// ============================================================
String generateHMAC(const String& message) {
  byte hmacResult[32];
  mbedtls_md_context_t ctx;
  mbedtls_md_type_t md_type = MBEDTLS_MD_SHA256;

  mbedtls_md_init(&ctx);
  mbedtls_md_setup(&ctx, mbedtls_md_info_from_type(md_type), 1);
  mbedtls_md_hmac_starts(&ctx,
    (const unsigned char*)FOTA_SECRET_KEY, strlen(FOTA_SECRET_KEY));
  mbedtls_md_hmac_update(&ctx,
    (const unsigned char*)message.c_str(), message.length());
  mbedtls_md_hmac_finish(&ctx, hmacResult);
  mbedtls_md_free(&ctx);

  String result = "";
  for (int i = 0; i < 32; i++) {
    char hex[3];
    sprintf(hex, "%02x", hmacResult[i]);
    result += hex;
  }
  return result;
}


void checkForUpdate() {
  WiFiClientSecure checkClient;
  checkClient.setCACert(CA_CERT);
  checkClient.setCertificate(CLIENT_CERT);
  checkClient.setPrivateKey(CLIENT_KEY);

  HTTPClient http;
  String url = String(FOTA_SERVER_URL) + "/check/" + DEVICE_ID;
  http.begin(checkClient, url);
  http.addHeader("X-Firmware-Version", FIRMWARE_VERSION);
  http.addHeader("X-Device-Signature", generateHMAC(DEVICE_ID));

  int code = http.GET();
  if (code == 200) {
    StaticJsonDocument<512> doc;
    deserializeJson(doc, http.getString());
    if (doc["update_available"].as<bool>()) {
      String newVer = doc["latest_version"].as<String>();
      Serial.printf("OTA dispo : v%s\n", newVer.c_str());
      otaUrl       = doc["download_url"].as<String>();
      otaRequested = true;
    }
  }
  http.end();
}


void performOTAUpdate(const String& url) {
  Serial.printf("OTA telechargement : %s\n", url.c_str());

  WiFiClientSecure otaClient;
  otaClient.setCACert(CA_CERT);
  otaClient.setCertificate(CLIENT_CERT);
  otaClient.setPrivateKey(CLIENT_KEY);

  StaticJsonDocument<128> doc;
  doc["device_id"] = DEVICE_ID;
  doc["status"]    = "downloading";
  doc["version"]   = FIRMWARE_VERSION;
  char buf[128];
  serializeJson(doc, buf);
  char ota_ack[72];
  snprintf(ota_ack, sizeof(ota_ack), "aqims/ota/%s/status", cfg_device_id);
  mqttClient.publish(ota_ack, buf);

  httpUpdate.setFollowRedirects(HTTPC_STRICT_FOLLOW_REDIRECTS);
  t_httpUpdate_return ret = httpUpdate.update(otaClient, url);

  switch (ret) {
    case HTTP_UPDATE_FAILED:
      Serial.printf("OTA echec : %s\n", httpUpdate.getLastErrorString().c_str());
      break;
    case HTTP_UPDATE_NO_UPDATES:
      Serial.println("OTA : pas de mise a jour");
      break;
    case HTTP_UPDATE_OK:
      Serial.println("OTA OK — redemarrage");
      break;
  }
}
