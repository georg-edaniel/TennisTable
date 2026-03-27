/*
  TableTennis — Collecte de données pour Edge Impulse
  ====================================================
  Envoie accX,accY,accZ,gyrX,gyrY,gyrZ à 50Hz sur le port série.
  Utiliser avec : edge-impulse-data-forwarder

  PROCÉDURE :
    1. Flasher ce sketch sur le Nano 33 BLE Rev 2
    2. Ouvrir un terminal : edge-impulse-data-forwarder
    3. Sélectionner le projet 839469
    4. Dans Edge Impulse Studio → Data acquisition
       - Choisir le label (BHdrive, BHsmash, FHdrive, FHloop, FHsmash)
       - Durée : 2000ms (2 secondes par coup)
       - Enregistrer 40-50 coups par classe
*/

#include <Arduino_BMI270_BMM150.h>

#define SAMPLE_RATE_HZ  50
#define INTERVAL_MS     (1000 / SAMPLE_RATE_HZ)  // 20ms

unsigned long lastSample = 0;

void setup() {
  Serial.begin(115200);
  while (!Serial);
  delay(500);

  if (!IMU.begin()) {
    Serial.println("ERR: IMU");
    while (1);
  }

  // Header requis par edge-impulse-data-forwarder
  // Format: "accX accY accZ gyrX gyrY gyrZ"
  Serial.println("Inertial Measurement Unit");
  Serial.println("accX accY accZ gyrX gyrY gyrZ");
}

void loop() {
  unsigned long now = millis();
  if (now - lastSample < INTERVAL_MS) return;
  lastSample = now;

  if (!IMU.accelerometerAvailable() || !IMU.gyroscopeAvailable()) return;

  float ax, ay, az, gx, gy, gz;
  IMU.readAccelerometer(ax, ay, az);
  IMU.readGyroscope(gx, gy, gz);

  // Format CSV attendu par le data-forwarder
  Serial.print(ax, 6); Serial.print(",");
  Serial.print(ay, 6); Serial.print(",");
  Serial.print(az, 6); Serial.print(",");
  Serial.print(gx, 6); Serial.print(",");
  Serial.print(gy, 6); Serial.print(",");
  Serial.println(gz, 6);
}
