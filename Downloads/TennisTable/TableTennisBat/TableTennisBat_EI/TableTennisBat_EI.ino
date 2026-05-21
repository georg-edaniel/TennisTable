/*
  TableTennis BLE v3 — Arduino Nano 33 BLE Rev 2
  ================================================
  Utilise le modèle Edge Impulse exporté (bibliothèque Arduino).

  PRÉREQUIS :
    1. Dans Edge Impulse Studio → Deployment
    2. Choisir "Arduino library" → Build
    3. Télécharger le .zip et l'installer :
       Arduino IDE → Sketch → Include Library → Add .ZIP Library
    4. Remplacer "table-tennis_inferencing.h" par le nom de ton projet EI

  CLASSES (doivent correspondre à ton projet EI) :
    0 = BHdrive
    1 = BHsmash
    2 = FHdrive
    3 = FHloop
    4 = FHsmash
    5 = zzz (repos)
*/

#include <ArduinoBLE.h>
#include <Arduino_BMI270_BMM150.h>
// !! Remplacer par le nom exact de ta bibliothèque Edge Impulse !!
#include <TennisTable_inferencing.h>

// ── Config ──────────────────────────────────────────────────────────────────
#define PLAYER_ID    2
#define DEVICE_NAME  "TableTennisBat2"

// ── BLE ─────────────────────────────────────────────────────────────────────
#define SERVICE_UUID      "19B10000-E8F2-537E-4F6C-D104768A1214"
#define STROKE_CHAR_UUID  "19B10001-E8F2-537E-4F6C-D104768A1214"

BLEService strokeService(SERVICE_UUID);
BLEByteCharacteristic strokeChar(STROKE_CHAR_UUID, BLERead | BLENotify);

// ── Buffer IMU pour Edge Impulse ─────────────────────────────────────────────
// EI_CLASSIFIER_DSP_INPUT_FRAME_SIZE = n_samples × n_axes
static float ei_buffer[EI_CLASSIFIER_DSP_INPUT_FRAME_SIZE];
static int   ei_buf_idx    = 0;
static bool  buf_full      = false;
#define SAMPLE_MS  (1000 / EI_CLASSIFIER_FREQUENCY)  // 20ms à 50Hz
#define COOLDOWN_MS  1200      // délai minimum entre 2 coups
#define ENERGY_MIN   3000.0f   // seuil énergie gyroscope — augmenter si trop sensible

unsigned long lastSample = 0;
unsigned long lastStroke = 0;

// ── Setup ────────────────────────────────────────────────────────────────────
void setup() {
  Serial.begin(115200);
  delay(1000);
  Serial.println("=== TableTennis BLE v3 (Edge Impulse) ===");
  Serial.print("Modele : "); Serial.println(EI_CLASSIFIER_PROJECT_NAME);
  Serial.print("Frequence : "); Serial.print(EI_CLASSIFIER_FREQUENCY); Serial.println(" Hz");
  Serial.print("Fenetre : "); Serial.print(EI_CLASSIFIER_RAW_SAMPLE_COUNT); Serial.println(" samples");

  pinMode(LED_BUILTIN, OUTPUT);
  digitalWrite(LED_BUILTIN, LOW);

  if (!IMU.begin()) {
    Serial.println("ERREUR: IMU !");
    while (1) { digitalWrite(LED_BUILTIN, !digitalRead(LED_BUILTIN)); delay(200); }
  }

  if (!BLE.begin()) {
    Serial.println("ERREUR: BLE !");
    while (1) { digitalWrite(LED_BUILTIN, !digitalRead(LED_BUILTIN)); delay(500); }
  }

  BLE.setLocalName(DEVICE_NAME);
  BLE.setDeviceName(DEVICE_NAME);
  BLE.setAdvertisedService(strokeService);
  strokeService.addCharacteristic(strokeChar);
  BLE.addService(strokeService);
  strokeChar.writeValue(255);
  BLE.advertise();
  Serial.println("Pret !");
}

// ── Loop ─────────────────────────────────────────────────────────────────────
void loop() {
  BLEDevice central = BLE.central();
  if (central) {
    Serial.print("Connecte: "); Serial.println(central.address());
    digitalWrite(LED_BUILTIN, HIGH);
    while (central.connected()) {
      collectAndInfer();
    }
    digitalWrite(LED_BUILTIN, LOW);
    Serial.println("Deconnecte");
  }
}

// ── Collecte + inférence EI ───────────────────────────────────────────────────
void collectAndInfer() {
  if (!IMU.gyroscopeAvailable() || !IMU.accelerationAvailable()) return;

  unsigned long now = millis();
  if (now - lastSample < SAMPLE_MS) return;
  lastSample = now;

  float ax, ay, az, gx, gy, gz, mx, my, mz;
  IMU.readAcceleration(ax, ay, az);
  IMU.readGyroscope(gx, gy, gz);
  if (IMU.magneticFieldAvailable()) {
    IMU.readMagneticField(mx, my, mz);
  } else {
    mx = my = mz = 0.0f;
  }

  // Remplir le buffer EI : [ax, ay, az, gx, gy, gz, mx, my, mz] × n_samples
  int base = ei_buf_idx * 9;
  ei_buffer[base + 0] = ax;
  ei_buffer[base + 1] = ay;
  ei_buffer[base + 2] = az;
  ei_buffer[base + 3] = gx;
  ei_buffer[base + 4] = gy;
  ei_buffer[base + 5] = gz;
  ei_buffer[base + 6] = mx;
  ei_buffer[base + 7] = my;
  ei_buffer[base + 8] = mz;

  ei_buf_idx++;
  if (ei_buf_idx >= EI_CLASSIFIER_RAW_SAMPLE_COUNT) {
    ei_buf_idx = 0;
    buf_full   = true;
  }
  if (!buf_full) return;

  // Vérification énergie (évite inférence sur fenêtre au repos)
  float energy = 0;
  for (int i = 0; i < EI_CLASSIFIER_RAW_SAMPLE_COUNT; i++) {
    int b = i * 9;
    float gxv = ei_buffer[b+3], gyv = ei_buffer[b+4], gzv = ei_buffer[b+5];
    energy += gxv*gxv + gyv*gyv + gzv*gzv;
  }
  if (energy < ENERGY_MIN) return;
  if (now - lastStroke < COOLDOWN_MS) return;

  // Inférence Edge Impulse
  signal_t signal;
  numpy::signal_from_buffer(ei_buffer, EI_CLASSIFIER_DSP_INPUT_FRAME_SIZE, &signal);

  ei_impulse_result_t result;
  EI_IMPULSE_ERROR err = run_classifier(&signal, &result, false);
  if (err != EI_IMPULSE_OK) {
    Serial.print("ERR classifier: "); Serial.println(err);
    return;
  }

  // Trouver la classe avec la meilleure probabilité
  int    best_cls   = 0;
  float  best_score = 0;
  for (size_t i = 0; i < EI_CLASSIFIER_LABEL_COUNT; i++) {
    if (result.classification[i].value > best_score) {
      best_score = result.classification[i].value;
      best_cls   = i;
    }
  }

  // Ignorer si confiance < 75% ou classe = "zzz"
  const char* label = result.classification[best_cls].label;
  if (best_score < 0.60f || strcmp(label, "zzz") == 0) return;

  lastStroke = now;

  // Vider le buffer — évite de ré-inférer le même coup sur les données résiduelles
  buf_full   = false;
  ei_buf_idx = 0;

  // Envoi BLE
  strokeChar.writeValue((uint8_t)best_cls);

  // Log
  Serial.print("COUP: "); Serial.print(label);
  Serial.print("  ("); Serial.print(best_score * 100, 0); Serial.println("%)");
  for (size_t i = 0; i < EI_CLASSIFIER_LABEL_COUNT; i++) {
    Serial.print("  "); Serial.print(result.classification[i].label);
    Serial.print(": "); Serial.println(result.classification[i].value, 2);
  }

  // Feedback LED
  for (int i = 0; i <= best_cls && i < 5; i++) {
    digitalWrite(LED_BUILTIN, LOW);  delay(50);
    digitalWrite(LED_BUILTIN, HIGH); delay(50);
  }
}
