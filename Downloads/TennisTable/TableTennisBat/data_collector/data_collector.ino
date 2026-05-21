/*
  TableTennis — Collecte de données pour Edge Impulse (9 axes)
  =============================================================
  Envoie accX,accY,accZ,gyrX,gyrY,gyrZ,magX,magY,magZ à 50Hz.
  Utiliser avec : edge-impulse-data-forwarder

  PROCÉDURE :
    1. Flasher ce sketch sur le Nano 33 BLE Rev 2
    2. Ouvrir un terminal : edge-impulse-data-forwarder
    3. Sélectionner le projet 839469
    4. Dans Edge Impulse Studio → Create Impulse :
       - Axes : accX, accY, accZ, gyrX, gyrY, gyrZ, magX, magY, magZ
    5. Dans Data acquisition :
       - Label (BHdrive, BHsmash, FHdrive, FHloop, FHsmash)
       - Durée : 2000ms | 40-50 coups par classe
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

  // Header requis par edge-impulse-data-forwarder (9 axes)
  Serial.println("Inertial Measurement Unit + Magnetometer");
  Serial.println("accX accY accZ gyrX gyrY gyrZ magX magY magZ");
}

void loop() {
  unsigned long now = millis();
  if (now - lastSample < INTERVAL_MS) return;
  lastSample = now;

  if (!IMU.accelerationAvailable() || !IMU.gyroscopeAvailable()) return;

  float ax, ay, az, gx, gy, gz, mx, my, mz;
  IMU.readAcceleration(ax, ay, az);
  IMU.readGyroscope(gx, gy, gz);

  // Magnétomètre — valeur 0 si non disponible ce cycle
  if (IMU.magneticFieldAvailable()) {
    IMU.readMagneticField(mx, my, mz);
  } else {
    mx = my = mz = 0.0f;
  }

  // Format CSV attendu par le data-forwarder
  Serial.print(ax, 6); Serial.print(",");
  Serial.print(ay, 6); Serial.print(",");
  Serial.print(az, 6); Serial.print(",");
  Serial.print(gx, 6); Serial.print(",");
  Serial.print(gy, 6); Serial.print(",");
  Serial.print(gz, 6); Serial.print(",");
  Serial.print(mx, 6); Serial.print(",");
  Serial.print(my, 6); Serial.print(",");
  Serial.println(mz, 6);
}
