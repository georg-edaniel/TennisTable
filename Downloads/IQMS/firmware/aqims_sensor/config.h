// ============================================================
//  AQIMS — Configuration ESP32
//  Modifiez ces valeurs selon votre installation
// ============================================================
#pragma once

// --- WiFi (géré par WiFiManager — ne pas mettre d'identifiants ici) ---
// Au premier démarrage : l'ESP32 crée un AP "AQIMS-Setup"
// Connecte-toi à cet AP, choisis ton réseau, les identifiants sont sauvegardés en flash.
// Pour réinitialiser : maintiens le bouton BOOT (GPIO0) appuyé 3 secondes au démarrage.
#define WIFI_AP_NAME      "AQIMS-Setup"   // Nom du portail de configuration
#define WIFI_AP_PASSWORD  "aqims1234"     // Mot de passe du portail (laisser vide = AP ouvert)
#define WIFI_RESET_PIN    0               // GPIO0 = bouton BOOT de l'ESP32 Thing Plus
#define WIFI_TIMEOUT_S    180             // Timeout portail : 3 min, puis redémarre

// --- MQTT (EMQX + TLS) ---
#define MQTT_HOST     "aqims.local"
#define MQTT_PORT     8883
#define MQTT_USERNAME "esp32_device"
#define MQTT_PASSWORD "changeme_mqtt_password"

// NOTE : les topics MQTT sont construits au runtime depuis l'ID appareil
//        (voir variables topic_sensors / topic_status / topic_ota / topic_config)

// --- Pins capteurs (brochage ENUMA PCB — IMG_3178) ---
// A0 → GPIO17 : DHT22  (Température + Humidité)    pull-up R2 10kΩ
// A1 → GPIO18 : LDR    (Luminosité)                diviseur R4 10kΩ
// A2 → GPIO19 : MQ7    (CO / Qualité air)          VBUS, R3 470Ω + R5 1kΩ
// GPIO23 (5_SCK) : DS18B20 (Temp. numérique 1-Wire) pull-up R1 4.7kΩ
#define PIN_DHT22      17   // A0 — Température + Humidité
#define PIN_LDR        18   // A1 — Luminosité (ADC)
#define PIN_MQ7        19   // A2 — CO / Qualité air (ADC, VBUS)
#define PIN_DS18B20    23   // GPIO23 (5_SCK) — Température 1-Wire

// --- Intervalles ---
#define SENSOR_INTERVAL_MS     10000    // Lecture capteurs toutes les 10 s
#define STATUS_INTERVAL_MS     60000    // Statut toutes les 60 s
#define WIFI_SCAN_INTERVAL_MS  60000    // Scan WiFi géolocalisation toutes les 60 s
#define OTA_CHECK_INTERVAL_MS  3600000  // Vérification OTA toutes les heures

// --- FOTA ---
#define FOTA_SERVER_URL  "https://aqims.local/api/v1/fota"
#define FOTA_SECRET_KEY  "changeme_fota_secret"
#define FIRMWARE_VERSION "1.0.0"
