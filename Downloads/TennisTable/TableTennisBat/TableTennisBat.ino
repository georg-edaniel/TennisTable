/*
  TableTennis BLE v2 — Arduino Nano 33 BLE Rev 2
  ================================================
  - IMU  : BMI270 + BMM150 (lib Arduino_BMI270_BMM150)
  - BLE  : ArduinoBLE
  - ML   : Random Forest 15 arbres, 16 features, 93.8% accuracy (CV)
  - Classes : BHdrive=0  BHsmash=1  FHdrive=2  FHloop=3  FHsmash=4  zzz=5

  Changer PLAYER_ID et DEVICE_NAME selon la raquette.
*/

#include <ArduinoBLE.h>
#include <Arduino_BMI270_BMM150.h>
#include "model.h"   // <-- classifieur exporté

// ── Config ──────────────────────────────────────────────────────────────────
#define PLAYER_ID    1
#define DEVICE_NAME  "TableTennisBat1"

// ── BLE ─────────────────────────────────────────────────────────────────────
#define SERVICE_UUID      "19B10000-E8F2-537E-4F6C-D104768A1214"
#define STROKE_CHAR_UUID  "19B10001-E8F2-537E-4F6C-D104768A1214"

BLEService strokeService(SERVICE_UUID);
BLEByteCharacteristic strokeChar(STROKE_CHAR_UUID, BLERead | BLENotify);

// ── Fenêtre de capture ───────────────────────────────────────────────────────
#define WINDOW_SIZE    25     // 25 samples × 20ms = 500ms
#define SAMPLE_MS      20     // 50 Hz
#define COOLDOWN_MS    400    // min entre 2 coups (réduit vs v1)
#define ENERGY_MIN     500.0f // seuil d'énergie pour déclencher la détection

float gx_buf[WINDOW_SIZE], gy_buf[WINDOW_SIZE], gz_buf[WINDOW_SIZE];
float ax_buf[WINDOW_SIZE], ay_buf[WINDOW_SIZE], az_buf[WINDOW_SIZE];
int   buf_idx      = 0;
bool  buf_full     = false;
unsigned long lastStrokeTime = 0;

// ── Setup ────────────────────────────────────────────────────────────────────
void setup() {
  Serial.begin(115200);
  delay(1000);
  Serial.println("=== TableTennis BLE v2 (ML) ===");
  Serial.print("Device: "); Serial.println(DEVICE_NAME);
  Serial.print("Model : "); Serial.print(N_TREES);
  Serial.print(" trees, "); Serial.print(N_FEATURES);
  Serial.println(" features");

  pinMode(LED_BUILTIN, OUTPUT);
  digitalWrite(LED_BUILTIN, LOW);

  if (!IMU.begin()) {
    Serial.println("ERREUR: IMU non detecte !");
    while (1) { digitalWrite(LED_BUILTIN, !digitalRead(LED_BUILTIN)); delay(200); }
  }
  Serial.print("IMU OK — gyro "); Serial.print(IMU.gyroscopeSampleRate()); Serial.println(" Hz");

  if (!BLE.begin()) {
    Serial.println("ERREUR: BLE non demarre !");
    while (1) { digitalWrite(LED_BUILTIN, !digitalRead(LED_BUILTIN)); delay(500); }
  }

  BLE.setLocalName(DEVICE_NAME);
  BLE.setDeviceName(DEVICE_NAME);
  BLE.setAdvertisedService(strokeService);
  strokeService.addCharacteristic(strokeChar);
  BLE.addService(strokeService);
  strokeChar.writeValue(255);  // aucun coup
  BLE.advertise();
  Serial.println("BLE advertising...");
}

// ── Loop ─────────────────────────────────────────────────────────────────────
void loop() {
  BLEDevice central = BLE.central();
  if (central) {
    Serial.print("Connecte: "); Serial.println(central.address());
    digitalWrite(LED_BUILTIN, HIGH);
    while (central.connected()) {
      collectAndClassify();
    }
    digitalWrite(LED_BUILTIN, LOW);
    Serial.println("Deconnecte");
  }
}

// ── Collecte + classification ─────────────────────────────────────────────────
void collectAndClassify() {
  if (!IMU.gyroscopeAvailable() || !IMU.accelerometerAvailable()) return;

  static unsigned long lastSample = 0;
  unsigned long now = millis();
  if (now - lastSample < SAMPLE_MS) return;
  lastSample = now;

  // Lire IMU
  float gx, gy, gz, ax, ay, az;
  IMU.readGyroscope(gx, gy, gz);
  IMU.readAccelerometer(ax, ay, az);

  // Stocker dans le buffer circulaire
  gx_buf[buf_idx] = gx;
  gy_buf[buf_idx] = gy;
  gz_buf[buf_idx] = gz;
  ax_buf[buf_idx] = ax;
  ay_buf[buf_idx] = ay;
  az_buf[buf_idx] = az;
  buf_idx++;
  if (buf_idx >= WINDOW_SIZE) { buf_idx = 0; buf_full = true; }
  if (!buf_full) return;

  // Calcul énergie gyro sur la fenêtre
  float energy = 0;
  for (int i = 0; i < WINDOW_SIZE; i++) {
    float mag = gx_buf[i]*gx_buf[i] + gy_buf[i]*gy_buf[i] + gz_buf[i]*gz_buf[i];
    energy += mag;
  }
  if (energy < ENERGY_MIN) return;             // fenêtre au repos
  if (now - lastStrokeTime < COOLDOWN_MS) return;  // cooldown

  // Extraire les 16 features
  float f[N_FEATURES];
  extractFeatures(f);

  // Classifier avec le Random Forest
  int cls = predict_stroke(f);

  // Ignorer "zzz" (repos détecté malgré énergie — rare)
  if (cls == 5) return;

  lastStrokeTime = now;

  // Envoi BLE
  strokeChar.writeValue((uint8_t)cls);

  // Log série
  Serial.print("COUP: "); Serial.print(CLASS_NAMES[cls]);
  Serial.print("  |  energie="); Serial.print(energy, 0);
  Serial.print("  |  peak_gyro="); Serial.println(f[0], 0);

  // Feedback LED : N clignotements = classe + 1
  for (int i = 0; i <= cls; i++) {
    digitalWrite(LED_BUILTIN, LOW);  delay(50);
    digitalWrite(LED_BUILTIN, HIGH); delay(50);
  }
}

// ── Extraction des 16 features ────────────────────────────────────────────────
// Doit correspondre EXACTEMENT à train_model.py / extract_features()
void extractFeatures(float* f) {
  // Magnitude gyro + accél
  float gyro_mag[WINDOW_SIZE], accel_mag[WINDOW_SIZE];
  for (int i = 0; i < WINDOW_SIZE; i++) {
    gyro_mag[i]  = sqrt(gx_buf[i]*gx_buf[i] + gy_buf[i]*gy_buf[i] + gz_buf[i]*gz_buf[i]);
    accel_mag[i] = sqrt(ax_buf[i]*ax_buf[i] + ay_buf[i]*ay_buf[i] + az_buf[i]*az_buf[i]);
  }

  // Pic gyro
  int peak_idx = 0;
  for (int i = 1; i < WINDOW_SIZE; i++)
    if (gyro_mag[i] > gyro_mag[peak_idx]) peak_idx = i;

  float peak_gm  = gyro_mag[peak_idx];
  float peak_gx_ = gx_buf[peak_idx];
  float peak_gy_ = gy_buf[peak_idx];
  float peak_gz_ = gz_buf[peak_idx];

  // RMS et énergie gyro
  float sum_sq = 0, energy = 0;
  for (int i = 0; i < WINDOW_SIZE; i++) {
    sum_sq += gyro_mag[i] * gyro_mag[i];
    energy += gyro_mag[i] * gyro_mag[i];
  }
  float rms_gyro = sqrt(sum_sq / WINDOW_SIZE);

  // Moyennes
  float mgx = 0, mgy = 0, mgz = 0;
  for (int i = 0; i < WINDOW_SIZE; i++) { mgx += gx_buf[i]; mgy += gy_buf[i]; mgz += gz_buf[i]; }
  mgx /= WINDOW_SIZE; mgy /= WINDOW_SIZE; mgz /= WINDOW_SIZE;

  // Pic accél
  int accel_peak = 0;
  for (int i = 1; i < WINDOW_SIZE; i++)
    if (accel_mag[i] > accel_mag[accel_peak]) accel_peak = i;

  float peak_am  = accel_mag[accel_peak];
  float peak_ax_ = ax_buf[accel_peak];
  float peak_ay_ = ay_buf[accel_peak];
  float peak_az_ = az_buf[accel_peak];

  float peak_timing = (float)peak_idx / (WINDOW_SIZE - 1);
  float denom = (abs(peak_gy_) > 0.001f) ? peak_gy_ : 0.001f;
  float ratio = peak_gx_ / denom;
  if (ratio >  50.0f) ratio =  50.0f;
  if (ratio < -50.0f) ratio = -50.0f;

  // Remplir le vecteur de features (ordre identique à train_model.py)
  f[0]  = peak_gm;
  f[1]  = peak_gx_;
  f[2]  = peak_gy_;
  f[3]  = peak_gz_;
  f[4]  = mgx;
  f[5]  = mgy;
  f[6]  = mgz;
  f[7]  = rms_gyro;
  f[8]  = peak_am;
  f[9]  = peak_ax_;
  f[10] = peak_ay_;
  f[11] = peak_az_;
  f[12] = energy;
  f[13] = peak_timing;
  f[14] = ratio;
  f[15] = (peak_gz_ >= 0) ? 1.0f : -1.0f;
}
