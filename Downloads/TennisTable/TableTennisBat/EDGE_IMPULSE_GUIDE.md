# Edge Impulse — Guide complet pour TT Tracker

## Projet existant
- URL    : https://studio.edgeimpulse.com/studio/839469
- API Key: ei_95b772f5a4c40a859b17e8e320b6639e0813efc29d0a045ba0f91c1c1f343cb2

---

## ÉTAPE 1 — Flasher le sketch de collecte

1. Ouvrir Arduino IDE
2. Ouvrir `TableTennisBat/data_collector/data_collector.ino`
3. Flasher sur le Nano 33 BLE Rev 2
4. Fermer le Moniteur Série si ouvert

---

## ÉTAPE 2 — Connecter le Data Forwarder

Dans un terminal Windows :
```
edge-impulse-data-forwarder --frequency 50
```
- Choisir le bon port COM
- Le CLI se connecte automatiquement au projet 839469

---

## ÉTAPE 3 — Collecter les données réelles

Sur https://studio.edgeimpulse.com/studio/839469 → **Data acquisition**

Pour chaque classe, enregistrer **40-50 échantillons de 2 secondes** :

| Label  | Geste à faire                              |
|--------|--------------------------------------------|
| BHdrive| Revers drive normal (5-6 fois par sample)  |
| BHsmash| Revers smash fort                          |
| FHdrive| Coup droit drive normal                    |
| FHloop | Coup droit avec effet (lift)               |
| FHsmash| Coup droit smash fort                      |
| zzz    | Raquette posée / aucun mouvement           |

**Conseils :**
- 2 secondes = 100 samples à 50Hz
- Faire UN seul coup au milieu des 2 secondes
- Varier la position (service, contre-attaque, frappe courte)
- Total : ~250 samples × 2s = ~8 minutes de collecte

---

## ÉTAPE 4 — Créer l'Impulse (modèle)

Dans **Create Impulse** :
1. **Input** : Time series — 2000ms, 50Hz, 6 axes (accX/Y/Z + gyrX/Y/Z)
2. **Processing** : Spectral Analysis (ou IMU → choisir "Flatten" si pas dispo)
3. **Learning** : Classification (NN)
4. Sauvegarder

Dans **Spectral features** → Generate features → vérifier que les classes sont bien séparées

Dans **Classifier** :
- 3 couches Dense (128 → 64 → 32)
- Dropout 0.2
- 100 epochs
- Objectif : >90% accuracy sur validation

---

## ÉTAPE 5 — Exporter vers Arduino

1. **Deployment** → Arduino library → Build
2. Télécharger le .zip (ex: `table-tennis_inferencing.zip`)
3. Arduino IDE → Sketch → Include Library → Add .ZIP Library

---

## ÉTAPE 6 — Flasher le firmware final

1. Ouvrir `TableTennisBat/TableTennisBat_EI.ino`
2. Remplacer la ligne :
   ```cpp
   #include <table-tennis_inferencing.h>
   ```
   Par le nom de ta bibliothèque EI (visible dans Arduino IDE → Sketch → Include Library)
3. Flasher → terminé !

---

## Résultats attendus

| Phase            | Précision estimée |
|------------------|-------------------|
| Modèle actuel v2 | 93.8% (synthétique) / ~80-87% réel |
| Après EI réel    | **90-96%** sur tes données          |
