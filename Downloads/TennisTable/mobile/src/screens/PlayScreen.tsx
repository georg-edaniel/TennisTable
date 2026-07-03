import React, { useCallback, useEffect, useRef, useState } from 'react';
import {
  Alert, Animated, Modal, PermissionsAndroid, Platform,
  ScrollView, Share, StyleSheet, Text, TextInput,
  TouchableOpacity, Vibration, View,
} from 'react-native';
import { BleManager, Device, Subscription } from 'react-native-ble-plx';
import { useFocusEffect } from '@react-navigation/native';
import { Ionicons } from '@expo/vector-icons';
import * as Haptics from 'expo-haptics';
import * as Speech from 'expo-speech';
import * as ScreenOrientation from 'expo-screen-orientation';
import Confetti from '../components/Confetti';
import CoinFlip from '../components/CoinFlip';
import TimeoutModal from '../components/TimeoutModal';
import WarmupTimer from '../components/WarmupTimer';
import MomentumChart from '../components/MomentumChart';
import BadgeCelebrationModal from '../components/BadgeCelebrationModal';
import StatShareCard from '../components/StatShareCard';
import { getEarnedBadges, BadgeDef } from '../services/badgeService';
import { playVictorySound } from '../services/soundService';
import { saveMatch, loadPlayerNames, savePlayerNames } from '../storage/matchStorage';
import { loadProfiles, updateProfile, updateStreaks } from '../storage/profileStorage';
import { saveTrainingSession } from '../storage/trainingStorage';
import { newElos } from '../services/eloService';
import {
  BG, CARD_BG, COLORS, STROKES, PlayerState, PlayerProfile,
  GameConfig, SetScore, emptyPlayer, countsToStrokes, PointLogEntry,
} from '../types';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { getRacketForPlayer, updateRacketLastUsed, updateRacketDeviceId, RacketInfo } from '../storage/racketStorage';

// ── BLE ──────────────────────────────────────────────────────────
const SERVICE    = '19B10000-E8F2-537E-4F6C-D104768A1214';
const CHAR       = '19B10001-E8F2-537E-4F6C-D104768A1214';
const BAT_SVC    = '0000180f-0000-1000-8000-00805f9b34fb';
const BAT_CHAR   = '00002a19-0000-1000-8000-00805f9b34fb';
const BAT_PREFIX = 'TableTennisBat';
const ACCENT     = '#6366f1';
const MAX_RECONNECT = 5;

function decodeByte(b64: string): number {
  const C = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/';
  return ((C.indexOf(b64[0]) << 2) | (C.indexOf(b64[1]) >> 4)) & 0xff;
}
const ble = new BleManager();

async function requestBlePermissions(): Promise<boolean> {
  if (Platform.OS !== 'android') return true;
  if (Platform.Version >= 31) {
    const res = await PermissionsAndroid.requestMultiple([
      PermissionsAndroid.PERMISSIONS.BLUETOOTH_SCAN,
      PermissionsAndroid.PERMISSIONS.BLUETOOTH_CONNECT,
      PermissionsAndroid.PERMISSIONS.ACCESS_FINE_LOCATION,
    ]);
    return Object.values(res).every(r => r === PermissionsAndroid.RESULTS.GRANTED);
  }
  return (await PermissionsAndroid.request(
    PermissionsAndroid.PERMISSIONS.ACCESS_FINE_LOCATION
  )) === PermissionsAndroid.RESULTS.GRANTED;
}

const DEFAULT_CONFIG: GameConfig = { pointsToWin: 11, numSets: 1 };

// ── Service rotation ─────────────────────────────────────────────
function getServer(
  score0: number, score1: number,
  pointsToWin: number, initialServer: 0 | 1
): 0 | 1 {
  const total = score0 + score1;
  const deucePts = pointsToWin - 1;
  const inDeuce = score0 >= deucePts && score1 >= deucePts;
  let block: number;
  if (inDeuce) {
    const deuceStart = 2 * deucePts;
    block = total - deuceStart;
  } else {
    block = Math.floor(total / 2);
  }
  return (block % 2 === 0 ? initialServer : (1 - initialServer) as 0 | 1);
}

function fmtSecs(s: number): string {
  const m = Math.floor(s / 60);
  return `${m}:${String(s % 60).padStart(2, '0')}`;
}

// ── Training drills ───────────────────────────────────────────────
const DRILL_TARGETS = [10, 20, 30, 50, 100];

export default function PlayScreen() {
  const [names, setNames] = useState<[string, string]>(['Joueur 1', 'Joueur 2']);
  const [editingName, setEditingName] = useState<number | null>(null);
  const [editVal, setEditVal] = useState('');
  const [players, setPlayers] = useState<[PlayerState, PlayerState]>([
    emptyPlayer('Joueur 1'), emptyPlayer('Joueur 2'),
  ]);
  const [winner, setWinner] = useState<number | null>(null);
  const [matchSaved, setMatchSaved] = useState(false);
  const [sets, setSets] = useState<SetScore[]>([]);
  const [profiles, setProfiles] = useState<PlayerProfile[]>([]);
  const [matchNote, setMatchNote] = useState('');

  // Config
  const [configVisible, setConfigVisible] = useState(false);
  const [config, setConfig] = useState<GameConfig>(DEFAULT_CONFIG);
  const [pendingConfig, setPendingConfig] = useState<GameConfig>(DEFAULT_CONFIG);

  // Profile picker
  const [profilePickerFor, setProfilePickerFor] = useState<number | null>(null);

  // Service rotation
  const initialServerRef = useRef<0 | 1>(0);
  const [showCoinFlip, setShowCoinFlip] = useState(false);

  // Timer
  const [timerSecs, setTimerSecs] = useState(0);
  const timerIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Undo history
  const historyRef = useRef<Array<{
    players: [PlayerState, PlayerState];
    sets: SetScore[];
    gameOver: boolean;
  }>>([]);

  // Training mode
  const [trainingVisible, setTrainingVisible] = useState(false);
  const [trainingStroke, setTrainingStroke] = useState(0);
  const [trainingTarget, setTrainingTarget] = useState(20);
  const [trainingCount, setTrainingCount] = useState(0);
  const [trainingActive, setTrainingActive] = useState(false);
  const trainingStartRef = useRef(Date.now());
  const [trainingTimer, setTrainingTimer] = useState(0);
  const trainingTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const [trainingProfileFor, setTrainingProfileFor] = useState<string | null>(null);

  const gameOverRef = useRef(false);
  const startTimeRef = useRef(Date.now());
  const devices = useRef<(Device | null)[]>([null, null]);
  const subs = useRef<(Subscription | null)[]>([null, null]);
  const reconnectCount = useRef<[number, number]>([0, 0]);
  const reconnectTimer = useRef<(ReturnType<typeof setTimeout> | null)[]>([null, null]);
  const scaleAnims = [useRef(new Animated.Value(1)).current, useRef(new Animated.Value(1)).current];

  // ELO prediction
  const [eloPred, setEloPred] = useState<[number, number] | null>(null);

  // Confetti
  const [showConfetti, setShowConfetti] = useState(false);

  // Speech enabled
  const [speechEnabled, setSpeechEnabled] = useState(false);

  // Landscape mode
  const [landscape, setLandscape] = useState(false);

  // Service timer (2 min chrono)
  const [serviceTimerActive, setServiceTimerActive] = useState(false);
  const [serviceTimerSecs, setServiceTimerSecs] = useState(120);
  const serviceTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Chalenge / contested point log
  const [chalenges, setChalenges] = useState<{ pi: number; score: string; timestamp: string }[]>([]);
  const [showChalenge, setShowChalenge] = useState(false);

  // Timeout (T.O.)
  const [timeoutVisible, setTimeoutVisible] = useState(false);

  // Point log & rally counter
  const [pointLog, setPointLog] = useState<PointLogEntry[]>([]);
  const rallyCountRef = useRef(0);   // nb frappes BLE depuis le dernier point

  // Score slide animations
  const slideAnims = [useRef(new Animated.Value(0)).current, useRef(new Animated.Value(0)).current];

  // Raquettes liées aux profils
  const [rackets, setRackets] = useState<[RacketInfo | null, RacketInfo | null]>([null, null]);

  // Serviette (towel) counter: every 6 points alert
  const totalPointsRef = useRef(0);

  // A1 – Service banner
  const [serviceBanner, setServiceBanner] = useState<string | null>(null);
  const prevServerRef = useRef<0 | 1 | null>(null);

  // A2 – Warm-up timer
  const [showWarmup, setShowWarmup] = useState(false);

  // A3 – Consecutive streak
  const [streaks, setStreaks] = useState<[number, number]>([0, 0]);
  const [streakOverlayMsg, setStreakOverlayMsg] = useState<string | null>(null);

  // A4 – Simulation mode
  const [simulationMode, setSimulationMode] = useState(false);

  // A5 – Momentum chart open
  const [showMomentum, setShowMomentum] = useState(false);

  // Badge celebration
  const [newBadges, setNewBadges] = useState<BadgeDef[]>([]);
  const [showBadgeCelebration, setShowBadgeCelebration] = useState(false);

  // Share winner profile
  const [showShare, setShowShare] = useState(false);
  const [shareProfile, setShareProfile] = useState<import('../types').PlayerProfile | null>(null);

  // F2 – Battery levels
  const [batteryLevels, setBatteryLevels] = useState<[number | null, number | null]>([null, null]);

  useFocusEffect(useCallback(() => {
    loadPlayerNames().then(([n1, n2]) => {
      setNames([n1, n2]);
      setPlayers([emptyPlayer(n1), emptyPlayer(n2)]);
    });
    loadProfiles().then(setProfiles);
    // Défi QR entrant
    AsyncStorage.getItem('@tt_challenge').then(raw => {
      if (!raw) return;
      AsyncStorage.removeItem('@tt_challenge');
      try {
        const { profileId, name } = JSON.parse(raw);
        setPlayers(prev => {
          const n = [...prev] as [PlayerState, PlayerState];
          n[1] = { ...n[1], name, profileId };
          return n;
        });
        setNames(prev => [prev[0], name] as [string, string]);
        getRacketForPlayer(profileId).then(r =>
          setRackets(prev => [prev[0], r] as [RacketInfo | null, RacketInfo | null])
        );
      } catch {}
    });
  }, []));

  // Timer
  useEffect(() => {
    timerIntervalRef.current = setInterval(() => {
      if (!gameOverRef.current) {
        setTimerSecs(Math.floor((Date.now() - startTimeRef.current) / 1000));
      }
    }, 1000);
    return () => { if (timerIntervalRef.current) clearInterval(timerIntervalRef.current); };
  }, []);

  // ELO prediction
  useEffect(() => {
    const p0 = players[0], p1 = players[1];
    if (p0.profileId && p1.profileId) {
      const pr0 = profiles.find(p => p.id === p0.profileId);
      const pr1 = profiles.find(p => p.id === p1.profileId);
      if (pr0 && pr1) {
        const exp0 = 1 / (1 + Math.pow(10, (pr1.elo - pr0.elo) / 400));
        setEloPred([Math.round(exp0 * 100), Math.round((1 - exp0) * 100)]);
        return;
      }
    }
    setEloPred(null);
  }, [players[0].profileId, players[1].profileId, profiles]);

  // Landscape toggle
  useEffect(() => {
    if (landscape) {
      ScreenOrientation.lockAsync(ScreenOrientation.OrientationLock.LANDSCAPE_LEFT).catch(() => {});
    } else {
      ScreenOrientation.lockAsync(ScreenOrientation.OrientationLock.PORTRAIT_UP).catch(() => {});
    }
  }, [landscape]);

  // Service timer countdown
  useEffect(() => {
    if (serviceTimerActive) {
      setServiceTimerSecs(120);
      serviceTimerRef.current = setInterval(() => {
        setServiceTimerSecs(prev => {
          if (prev <= 1) {
            clearInterval(serviceTimerRef.current!);
            setServiceTimerActive(false);
            Haptics.notificationAsync(Haptics.NotificationFeedbackType.Warning).catch(() => {});
            return 0;
          }
          return prev - 1;
        });
      }, 1000);
    } else {
      if (serviceTimerRef.current) clearInterval(serviceTimerRef.current);
    }
    return () => { if (serviceTimerRef.current) clearInterval(serviceTimerRef.current); };
  }, [serviceTimerActive]);

  useEffect(() => () => {
    subs.current.forEach(s => s?.remove());
    devices.current.forEach(d => d?.cancelConnection().catch(() => {}));
    reconnectTimer.current.forEach(t => { if (t) clearTimeout(t); });
    if (timerIntervalRef.current) clearInterval(timerIntervalRef.current);
    if (trainingTimerRef.current) clearInterval(trainingTimerRef.current);
    if (serviceTimerRef.current) clearInterval(serviceTimerRef.current);
    ScreenOrientation.lockAsync(ScreenOrientation.OrientationLock.PORTRAIT_UP).catch(() => {});
  }, []);

  // ── Noms ──────────────────────────────────────────────────────
  function startEdit(pi: number) { setEditingName(pi); setEditVal(names[pi]); }
  function confirmEdit() {
    if (editingName === null) return;
    const t = editVal.trim() || `Joueur ${editingName + 1}`;
    const newNames: [string, string] = editingName === 0 ? [t, names[1]] : [names[0], t];
    setNames(newNames);
    savePlayerNames(newNames[0], newNames[1]);
    setPlayers(prev => {
      const next = [...prev] as [PlayerState, PlayerState];
      next[editingName] = { ...next[editingName], name: t };
      return next;
    });
    setEditingName(null);
  }

  // ── BLE auto-reconnect ─────────────────────────────────────────
  const connectBLE = useCallback(async (pi: number, isAutoReconnect = false) => {
    if (!await requestBlePermissions()) {
      Alert.alert('Permission refusée', 'Active le Bluetooth dans les paramètres.'); return;
    }
    subs.current[pi]?.remove(); subs.current[pi] = null;
    devices.current[pi]?.cancelConnection().catch(() => {}); devices.current[pi] = null;
    if (!isAutoReconnect) reconnectCount.current[pi] = 0;

    setPlayers(prev => {
      const n = [...prev] as [PlayerState, PlayerState];
      n[pi] = { ...n[pi], scanning: true, connected: false };
      return n;
    });

    // Récupère le deviceId associé à ce joueur (si configuré dans les paramètres raquette)
    const targetDeviceId = rackets[pi]?.deviceId ?? null;

    let found = false;
    ble.startDeviceScan(null, { allowDuplicates: false }, async (err, device) => {
      if (err || found || !device?.name?.startsWith(BAT_PREFIX)) return;
      // Si un deviceId spécifique est configuré, ne connecter qu'à ce device
      if (targetDeviceId && device.id !== targetDeviceId) return;
      found = true; ble.stopDeviceScan();
      try {
        const conn = await device.connect({ autoConnect: false });
        await conn.discoverAllServicesAndCharacteristics();
        devices.current[pi] = conn;
        reconnectCount.current[pi] = 0;

        const sub = conn.monitorCharacteristicForService(SERVICE, CHAR, (e, c) => {
          if (e || !c?.value) return;
          const val = decodeByte(c.value);
          if (val < 5) {
            if (!gameOverRef.current) {
              rallyCountRef.current += 1;  // count rally strokes
              setPlayers(prev => {
                const n = [...prev] as [PlayerState, PlayerState];
                const counts = [...n[pi].counts] as PlayerState['counts'];
                counts[val]++;
                n[pi] = { ...n[pi], counts, lastStroke: val };
                return n;
              });
              Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light).catch(() => {});
            }
            // Training mode
            if (trainingActive && val === trainingStroke) {
              setTrainingCount(c => {
                const next = c + 1;
                if (next >= trainingTarget) {
                  Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success).catch(() => {});
                }
                return next;
              });
            }
          }
        });
        subs.current[pi] = sub;
        setPlayers(prev => {
          const n = [...prev] as [PlayerState, PlayerState];
          n[pi] = { ...n[pi], connected: true, scanning: false, reconnectMsg: '' };
          return n;
        });

        // Mémorise le deviceId pour les connexions futures (distinction raquette 1 / raquette 2)
        const currentRacket = rackets[pi];
        if (currentRacket && currentRacket.deviceId !== device.id) {
          updateRacketDeviceId(currentRacket.id, device.id).catch(() => {});
          setRackets(prev => {
            const n = [...prev] as [RacketInfo | null, RacketInfo | null];
            n[pi] = { ...currentRacket, deviceId: device.id };
            return n;
          });
        }

        // F2 – Read battery level (silently ignore if absent)
        try {
          const batChar = await conn.readCharacteristicForService(BAT_SVC, BAT_CHAR);
          if (batChar?.value) {
            const lvl = decodeByte(batChar.value);
            setBatteryLevels(prev => {
              const n = [...prev] as [number | null, number | null];
              n[pi] = Math.min(100, Math.max(0, lvl));
              return n;
            });
          }
        } catch { /* Battery Service not present */ }

        conn.onDisconnected(() => {
          devices.current[pi] = null;
          const count = reconnectCount.current[pi];
          if (!gameOverRef.current && count < MAX_RECONNECT) {
            const attempt = count + 1;
            reconnectCount.current[pi] = attempt;
            const delay = 2000 * attempt;
            setPlayers(prev => {
              const n = [...prev] as [PlayerState, PlayerState];
              n[pi] = { ...n[pi], connected: false, reconnectMsg: `Reconnexion ${attempt}/${MAX_RECONNECT}…` };
              return n;
            });
            reconnectTimer.current[pi] = setTimeout(() => connectBLE(pi, true), delay);
          } else {
            setPlayers(prev => {
              const n = [...prev] as [PlayerState, PlayerState];
              n[pi] = { ...n[pi], connected: false, reconnectMsg: '' };
              return n;
            });
          }
        });
      } catch {
        setPlayers(prev => {
          const n = [...prev] as [PlayerState, PlayerState];
          n[pi] = { ...n[pi], scanning: false };
          return n;
        });
        if (!isAutoReconnect) Alert.alert('Connexion échouée', 'Vérifie que la raquette est allumée et proche.');
      }
    });
    setTimeout(() => {
      if (!found) {
        ble.stopDeviceScan();
        setPlayers(prev => {
          const n = [...prev] as [PlayerState, PlayerState];
          n[pi] = { ...n[pi], scanning: false };
          return n;
        });
        if (!isAutoReconnect) Alert.alert('Raquette introuvable', 'Allume la raquette et réessaie.');
      }
    }, 10_000);
  }, [trainingActive, trainingStroke, trainingTarget]);

  // ── Point & Sets ──────────────────────────────────────────────
  const addPoint = useCallback((pi: number) => {
    if (gameOverRef.current) return;

    // A3 – Update consecutive streak
    setStreaks(prev => {
      const n: [number, number] = [prev[0], prev[1]];
      n[pi] = prev[pi] + 1;
      n[1 - pi] = 0;
      const newStreak = n[pi];
      if (newStreak >= 3) {
        const msg = `🔥 ${newStreak} de suite !`;
        setStreakOverlayMsg(msg);
        setTimeout(() => setStreakOverlayMsg(null), 2000);
      }
      return n;
    });

    // Capture rally count and reset
    const currentRally = rallyCountRef.current;
    rallyCountRef.current = 0;

    // Push to undo history (use current state from ref)
    historyRef.current = [
      ...historyRef.current.slice(-9),
      {
        players: JSON.parse(JSON.stringify(players)) as [PlayerState, PlayerState],
        sets: [...sets],
        gameOver: false,
      },
    ];

    let newWinner: number | null = null;
    const { pointsToWin, numSets } = config;
    const setsNeeded = Math.ceil(numSets / 2);

    setPlayers(prev => {
      const n = [...prev] as [PlayerState, PlayerState];
      const newScore = n[pi].score + 1;
      const otherScore = n[1 - pi].score;
      n[pi] = { ...n[pi], score: newScore };

      if (newScore >= pointsToWin && (newScore - otherScore) >= 2) {
        const newSetsWon = n[pi].setsWon + 1;
        n[pi] = { ...n[pi], setsWon: newSetsWon };
        setSets(prev => [...prev, {
          score1: pi === 0 ? newScore : otherScore,
          score2: pi === 1 ? newScore : otherScore,
        }]);
        if (newSetsWon >= setsNeeded) {
          newWinner = pi;
          gameOverRef.current = true;
        } else {
          n[0] = { ...n[0], score: 0 };
          n[1] = { ...n[1], score: 0 };
        }
      }
      return n;
    });

    // Serviette every 6 points (ITTF rule)
    totalPointsRef.current += 1;
    if (totalPointsRef.current > 0 && totalPointsRef.current % 6 === 0) {
      Haptics.notificationAsync(Haptics.NotificationFeedbackType.Warning).catch(() => {});
      Alert.alert('🧻 Serviette', 'Les joueurs peuvent s\'essuyer (toutes les 6 points)', [{ text: 'OK' }]);
    }

    // A1 – Detect service change and show banner
    setPlayers(current => {
      const newServer = getServer(current[0].score, current[1].score, config.pointsToWin, initialServerRef.current);
      if (prevServerRef.current !== null && prevServerRef.current !== newServer) {
        const serverName = current[newServer].name;
        setServiceBanner(`🏓 Service de ${serverName}`);
        setTimeout(() => setServiceBanner(null), 2500);
        Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light).catch(() => {});
      }
      prevServerRef.current = newServer;
      return current;
    });

    // Record in pointLog
    setPlayers(current => {
      const s0 = current[0].score, s1 = current[1].score;
      setPointLog(prev => [...prev, {
        time: Date.now() - startTimeRef.current,
        player: pi as 0 | 1,
        score: [s0, s1],
        rally: currentRally,
      }]);
      return current;
    });

    if (newWinner !== null) {
      setWinner(newWinner);
      setShowConfetti(true);
      setTimeout(() => setShowConfetti(false), 3000);
      Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success).catch(() => {});
      playVictorySound('fanfare').catch(() => {});
    } else {
      Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium).catch(() => {});
    }
    // Scale + slide animation on score
    // Spring bounce sur le score
    scaleAnims[pi].setValue(1.5);
    Animated.spring(scaleAnims[pi], {
      toValue: 1, useNativeDriver: true,
      speed: 18, bounciness: 14,
    }).start();
    // Slide depuis le haut
    slideAnims[pi].setValue(-20);
    Animated.spring(slideAnims[pi], {
      toValue: 0, useNativeDriver: true,
      speed: 20, bounciness: 10,
    }).start();
    // Speech announcement
    if (speechEnabled) {
      setPlayers(current => {
        const s0 = current[0].score, s1 = current[1].score;
        const deuce = s0 === s1 && s0 >= config.pointsToWin - 1;
        const avt = !deuce && (s0 >= config.pointsToWin - 1 || s1 >= config.pointsToWin - 1) && Math.abs(s0 - s1) === 1;
        if (deuce) Speech.speak('Égalité', { language: 'fr-FR' });
        else if (avt) Speech.speak(s0 > s1 ? `Avantage ${current[0].name}` : `Avantage ${current[1].name}`, { language: 'fr-FR' });
        else Speech.speak(`${s0} à ${s1}`, { language: 'fr-FR' });
        return current;
      });
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [config, players, sets]);

  // ── Undo ─────────────────────────────────────────────────────
  function addChalenge(pi: number) {
    const [p0, p1] = players;
    const score = `${p0.score}–${p1.score}`;
    setChalenges(prev => [...prev, { pi, score, timestamp: new Date().toLocaleTimeString('fr-FR') }]);
    setShowChalenge(true);
    Haptics.notificationAsync(Haptics.NotificationFeedbackType.Warning).catch(() => {});
  }

  function undo() {
    if (historyRef.current.length === 0) return;
    const last = historyRef.current[historyRef.current.length - 1];
    historyRef.current = historyRef.current.slice(0, -1);
    gameOverRef.current = false;
    setWinner(null);
    setMatchSaved(false);
    setPlayers(last.players);
    setSets(last.sets);
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light).catch(() => {});
  }

  async function handleSaveAndNew() {
    if (!matchSaved && winner !== null) {
      const [p0, p1] = players;
      let eloChange1: number | undefined;
      let eloChange2: number | undefined;

      if (p0.profileId && p1.profileId) {
        const prof0 = profiles.find(p => p.id === p0.profileId);
        const prof1 = profiles.find(p => p.id === p1.profileId);
        if (prof0 && prof1) {
          const [newE1, newE2, d1, d2] = newElos(prof0.elo, prof1.elo, winner as 0 | 1);
          eloChange1 = d1; eloChange2 = d2;
          await updateProfile({ ...prof0, elo: newE1, wins: prof0.wins + (winner === 0 ? 1 : 0), losses: prof0.losses + (winner === 1 ? 1 : 0) });
          await updateProfile({ ...prof1, elo: newE2, wins: prof1.wins + (winner === 1 ? 1 : 0), losses: prof1.losses + (winner === 0 ? 1 : 0) });
          await updateStreaks(p0.profileId, winner === 0);
          await updateStreaks(p1.profileId, winner === 1);
          const oldBadgeIds0 = getEarnedBadges(prof0).map(b => b.id);
          const oldBadgeIds1 = getEarnedBadges(prof1).map(b => b.id);
          const freshProfiles = await loadProfiles();
          setProfiles(freshProfiles);
          const freshP0 = freshProfiles.find(p => p.id === p0.profileId);
          const freshP1 = freshProfiles.find(p => p.id === p1.profileId);
          const earned: BadgeDef[] = [];
          if (freshP0) getEarnedBadges(freshP0).forEach(b => { if (!oldBadgeIds0.includes(b.id)) earned.push(b); });
          if (freshP1) getEarnedBadges(freshP1).forEach(b => { if (!oldBadgeIds1.includes(b.id)) earned.push(b); });
          if (earned.length > 0) { setNewBadges(earned); setShowBadgeCelebration(true); }
        }
      }

      const rallyLengths = pointLog.map(e => e.rally).filter(r => r > 0);
      await saveMatch({
        id: Date.now().toString(), date: new Date().toISOString(),
        player1: p0.name, player2: p1.name,
        score1: config.numSets > 1 ? p0.setsWon : p0.score,
        score2: config.numSets > 1 ? p1.setsWon : p1.score,
        winner: winner as 0 | 1,
        durationSecs: Math.round((Date.now() - startTimeRef.current) / 1000),
        strokes1: countsToStrokes(p0.counts), strokes2: countsToStrokes(p1.counts),
        config, sets,
        profile1Id: p0.profileId ?? undefined,
        profile2Id: p1.profileId ?? undefined,
        eloChange1, eloChange2,
        note: matchNote.trim() || undefined,
        pointLog: pointLog.length > 0 ? pointLog : undefined,
        rallyLengths: rallyLengths.length > 0 ? rallyLengths : undefined,
      });
      setMatchSaved(true);
      // Mettre à jour la dernière utilisation des raquettes
      for (const r of rackets) {
        if (r) updateRacketLastUsed(r.id).catch(() => {});
      }
    }
    newGame();
  }

  function newGame() {
    gameOverRef.current = false; setWinner(null); setMatchSaved(false);
    startTimeRef.current = Date.now(); setTimerSecs(0);
    setSets([]); setMatchNote('');
    historyRef.current = [];
    totalPointsRef.current = 0;
    setPointLog([]);
    rallyCountRef.current = 0;
    setStreaks([0, 0]);
    setServiceBanner(null);
    prevServerRef.current = null;
    // Coin flip for new server
    const server = (Math.random() < 0.5 ? 0 : 1) as 0 | 1;
    initialServerRef.current = server;
    setShowCoinFlip(true);
    setTimeout(() => setShowCoinFlip(false), 2000);
    setPlayers(prev => {
      const n = [...prev] as [PlayerState, PlayerState];
      for (let i = 0; i < 2; i++) n[i] = { ...n[i], score: 0, setsWon: 0, counts: [0, 0, 0, 0, 0], lastStroke: null };
      return n;
    });
    // A2 – Show warm-up timer
    setShowWarmup(true);
  }

  function openConfig() { setPendingConfig(config); setConfigVisible(true); }
  function applyConfig() { setConfig(pendingConfig); setConfigVisible(false); newGame(); }

  // ── Training ─────────────────────────────────────────────────
  function startTraining() {
    setTrainingCount(0);
    trainingStartRef.current = Date.now();
    setTrainingTimer(0);
    setTrainingActive(true);
    if (trainingTimerRef.current) clearInterval(trainingTimerRef.current);
    trainingTimerRef.current = setInterval(() => {
      setTrainingTimer(Math.floor((Date.now() - trainingStartRef.current) / 1000));
    }, 1000);
  }

  async function stopTraining() {
    setTrainingActive(false);
    if (trainingTimerRef.current) { clearInterval(trainingTimerRef.current); trainingTimerRef.current = null; }
    const dur = Math.floor((Date.now() - trainingStartRef.current) / 1000);
    await saveTrainingSession({
      id: Date.now().toString(),
      date: new Date().toISOString(),
      profileId: trainingProfileFor,
      stroke: STROKES[trainingStroke].name,
      target: trainingTarget,
      completed: trainingCount,
      durationSecs: dur,
    });
    setTrainingVisible(false);
    Alert.alert('Entraînement terminé', `${trainingCount}/${trainingTarget} coups en ${fmtSecs(dur)}`);
  }

  const [p0, p1] = players;
  const setsNeeded = Math.ceil(config.numSets / 2);
  const currentServer = getServer(p0.score, p1.score, config.pointsToWin, initialServerRef.current);
  const hasHistory = historyRef.current.length > 0;

  // DEUCE / AVANTAGE
  const deuceThreshold = config.pointsToWin - 1;
  const inDeuce = p0.score === p1.score && p0.score >= deuceThreshold;
  const inAdv = !inDeuce && p0.score >= deuceThreshold && p1.score >= deuceThreshold && Math.abs(p0.score - p1.score) === 1;
  const advPlayer = inAdv ? (p0.score > p1.score ? p0.name : p1.name) : null;

  return (
    <View style={s.root}>
      {/* Confetti overlay */}
      <Confetti active={showConfetti} />

      {/* A2 – Warm-up Timer */}
      <WarmupTimer visible={showWarmup} onDone={() => setShowWarmup(false)} />

      {/* A3 – Streak overlay */}
      {streakOverlayMsg && (
        <View style={s.streakOverlay} pointerEvents="none">
          <Text style={s.streakOverlayTxt}>{streakOverlayMsg}</Text>
        </View>
      )}

      {/* A1 – Service banner */}
      {serviceBanner && (
        <View style={s.serviceBanner} pointerEvents="none">
          <Text style={s.serviceBannerTxt}>{serviceBanner}</Text>
        </View>
      )}

      {/* Top bar */}
      <View style={s.topBar}>
        <View style={s.setInfo}>
          <Text style={s.setInfoTxt}>
            {config.numSets > 1 ? `Best of ${config.numSets} · ${config.pointsToWin} pts` : `${config.pointsToWin} pts · écart 2`}
          </Text>
          {config.numSets > 1 && <Text style={s.setsScore}>{p0.setsWon} – {p1.setsWon} sets</Text>}
        </View>
        <View style={s.topActions}>
          {/* Timer */}
          <View style={s.timerBox}>
            <Ionicons name="timer-outline" size={12} color="#475569" />
            <Text style={s.timerTxt}>{fmtSecs(timerSecs)}</Text>
          </View>
          {/* Undo */}
          <TouchableOpacity style={[s.topBtn, !hasHistory && { opacity: 0.3 }]} onPress={undo} disabled={!hasHistory} accessibilityRole="button" accessibilityLabel="Annuler le dernier point">
            <Ionicons name="arrow-undo" size={16} color="#f59e0b" />
          </TouchableOpacity>
          {/* Timeout */}
          <TouchableOpacity
            style={[s.topBtn, { borderColor: '#f59e0b50', backgroundColor: '#f59e0b08' }]}
            onPress={() => setTimeoutVisible(true)}
          >
            <Text style={{ fontSize: 9, fontWeight: '900', color: '#f59e0b' }}>T.O.</Text>
          </TouchableOpacity>
          {/* Training */}
          <TouchableOpacity style={s.topBtn} onPress={() => setTrainingVisible(true)}>
            <Ionicons name="fitness-outline" size={16} color="#22c55e" />
          </TouchableOpacity>
          {/* Chalenge log */}
          {chalenges.length > 0 && (
            <TouchableOpacity style={[s.topBtn, { borderColor: '#f59e0b60', backgroundColor: '#f59e0b10' }]}
              onPress={() => setShowChalenge(true)}>
              <Text style={{ fontSize: 10, fontWeight: '800', color: '#f59e0b' }}>{chalenges.length}⚡</Text>
            </TouchableOpacity>
          )}
          {/* Service timer */}
          <TouchableOpacity
            style={[s.topBtn, serviceTimerActive && { borderColor: '#f59e0b', backgroundColor: '#f59e0b15' }]}
            onPress={() => setServiceTimerActive(v => !v)}
          >
            {serviceTimerActive
              ? <Text style={{ fontSize: 10, fontWeight: '800', color: '#f59e0b' }}>{serviceTimerSecs}s</Text>
              : <Ionicons name="stopwatch-outline" size={16} color="#475569" />
            }
          </TouchableOpacity>
          {/* Speech */}
          <TouchableOpacity style={[s.topBtn, speechEnabled && { borderColor: '#38bdf8', backgroundColor: '#38bdf815' }]}
            onPress={() => setSpeechEnabled(v => !v)}>
            <Ionicons name={speechEnabled ? 'volume-high' : 'volume-mute'} size={16}
              color={speechEnabled ? '#38bdf8' : '#475569'} />
          </TouchableOpacity>
          {/* Landscape */}
          <TouchableOpacity style={[s.topBtn, landscape && { borderColor: ACCENT, backgroundColor: ACCENT + '15' }]}
            onPress={() => setLandscape(v => !v)}>
            <Ionicons name="phone-landscape-outline" size={16} color={landscape ? ACCENT : '#475569'} />
          </TouchableOpacity>
          {/* Config */}
          <TouchableOpacity style={s.topBtn} onPress={openConfig}>
            <Ionicons name="settings-outline" size={16} color="#94a3b8" />
          </TouchableOpacity>
        </View>
      </View>

      {/* Coin flip modal */}
      <CoinFlip
        visible={showCoinFlip}
        serverName={players[initialServerRef.current].name}
        onDone={() => setShowCoinFlip(false)}
      />

      {/* Timeout modal */}
      <TimeoutModal visible={timeoutVisible} onClose={() => setTimeoutVisible(false)} />

      {/* ELO prediction */}
      {eloPred && (
        <View style={s.eloPredRow}>
          <Text style={[s.eloPredTxt, { color: COLORS[0] }]}>{p0.name} {eloPred[0]}%</Text>
          <Text style={s.eloPredSep}>·</Text>
          <Text style={[s.eloPredTxt, { color: COLORS[1] }]}>{p1.name} {eloPred[1]}%</Text>
        </View>
      )}

      {/* DEUCE / AVANTAGE */}
      {(inDeuce || inAdv) && (
        <View style={[s.deuceBanner, inAdv && { backgroundColor: '#f59e0b20', borderColor: '#f59e0b60' }]}>
          <Text style={[s.deuceTxt, inAdv && { color: '#f59e0b' }]}>
            {inDeuce ? '⚖️  ÉGALITÉ' : `⚡ AVT ${advPlayer?.toUpperCase()}`}
          </Text>
        </View>
      )}

      {/* A4 – Simulation mode banner */}
      {simulationMode && (
        <View style={s.simBanner}>
          <Ionicons name="game-controller-outline" size={12} color="#f59e0b" />
          <Text style={s.simBannerTxt}>Mode Simulation — pas de BLE</Text>
          <TouchableOpacity onPress={() => setSimulationMode(false)}>
            <Text style={{ fontSize: 11, color: '#f59e0b', fontWeight: '700' }}>Désactiver</Text>
          </TouchableOpacity>
        </View>
      )}

      {/* A5 – Momentum chart */}
      {pointLog.length > 0 && (
        <View style={s.momentumSection}>
          <TouchableOpacity style={s.momentumHeader} onPress={() => setShowMomentum(v => !v)}>
            <Ionicons name="analytics-outline" size={13} color="#64748b" />
            <Text style={s.momentumTitle}>Momentum (10 derniers pts)</Text>
            <Ionicons name={showMomentum ? 'chevron-up' : 'chevron-down'} size={13} color="#64748b" />
          </TouchableOpacity>
          {showMomentum && (
            <MomentumChart
              pointLog={pointLog}
              color1={COLORS[0]}
              color2={COLORS[1]}
              name1={p0.name}
              name2={p1.name}
            />
          )}
        </View>
      )}

      {/* Score */}
      <View style={s.scoreSec}>
        <View style={s.scorePlayerLabel}>
          <View style={[s.dot, { backgroundColor: COLORS[0] }]} />
          <Text style={[s.scoreLabel, { color: COLORS[0] }]} numberOfLines={1}>{p0.name}</Text>
          {currentServer === 0 && <Text style={s.serveIndicator}>🏓</Text>}
        </View>
        <View style={s.scoreCenter}>
          <Animated.Text style={[s.scoreNum, { color: COLORS[0], transform: [{ scale: scaleAnims[0] }, { translateY: slideAnims[0] }] }]}>{p0.score}</Animated.Text>
          <Text style={s.scoreSep}>–</Text>
          <Animated.Text style={[s.scoreNum, { color: COLORS[1], transform: [{ scale: scaleAnims[1] }, { translateY: slideAnims[1] }] }]}>{p1.score}</Animated.Text>
        </View>
        <View style={[s.scorePlayerLabel, { justifyContent: 'flex-end' }]}>
          {currentServer === 1 && <Text style={s.serveIndicator}>🏓</Text>}
          <Text style={[s.scoreLabel, { color: COLORS[1] }]} numberOfLines={1}>{p1.name}</Text>
          <View style={[s.dot, { backgroundColor: COLORS[1] }]} />
        </View>
      </View>

      <View style={[s.players, { flex: 1 }]}>
        {([p0, p1] as PlayerState[]).map((p, pi) => (
          <View key={pi} style={[s.card, p.connected && { borderColor: COLORS[pi] }]}>
            {/* Profile picker */}
            <TouchableOpacity style={s.profileRow} onPress={() => setProfilePickerFor(pi)}>
              <Ionicons name="person-circle-outline" size={14} color={p.profileId ? COLORS[pi] : '#475569'} />
              <Text style={[s.profileTxt, p.profileId && { color: COLORS[pi] }]} numberOfLines={1}>
                {p.profileId ? profiles.find(pr => pr.id === p.profileId)?.name ?? 'Profil' : 'Lier un profil'}
              </Text>
              <Ionicons name="chevron-down" size={11} color="#475569" />
            </TouchableOpacity>

            {/* Raquette + batterie sur une ligne */}
            {(rackets[pi] || batteryLevels[pi] !== null) && (
              <View style={s.racketRow}>
                {rackets[pi] && <>
                  <Ionicons name="ellipse" size={8} color={COLORS[pi]} />
                  <Text style={[s.racketTxt, { color: COLORS[pi] }]}>🏓 {rackets[pi]!.name}</Text>
                </>}
                {batteryLevels[pi] !== null && (
                  <Text style={[s.racketTxt, { color: batteryLevels[pi]! > 20 ? '#22c55e' : '#f87171', marginLeft: 'auto' }]}>
                    🔋 {batteryLevels[pi]}%
                  </Text>
                )}
              </View>
            )}

            {/* Nom */}
            {editingName === pi ? (
              <View style={s.nameEditRow}>
                <TextInput style={[s.nameInput, { borderColor: COLORS[pi] }]} value={editVal}
                  onChangeText={setEditVal} autoFocus onSubmitEditing={confirmEdit}
                  returnKeyType="done" maxLength={16} placeholderTextColor="#475569" />
                <TouchableOpacity style={[s.nameOkBtn, { backgroundColor: COLORS[pi] }]} onPress={confirmEdit}>
                  <Ionicons name="checkmark" size={16} color="#fff" />
                </TouchableOpacity>
              </View>
            ) : (
              <TouchableOpacity onPress={() => startEdit(pi)} style={s.nameRow}>
                <View style={[s.playerTag, { backgroundColor: COLORS[pi] + '20', borderColor: COLORS[pi] + '60' }]}>
                  <Text style={[s.playerName, { color: COLORS[pi] }]}>{p.name}</Text>
                </View>
                <Ionicons name="pencil" size={12} color="#475569" style={{ marginLeft: 6 }} />
                {currentServer === pi && <Text style={{ marginLeft: 4, fontSize: 10, color: '#f59e0b', fontWeight: '700' }}>SERT</Text>}
              </TouchableOpacity>
            )}

            {/* Sets dots */}
            {config.numSets > 1 && (
              <View style={s.setsRow}>
                {Array.from({ length: setsNeeded }).map((_, i) => (
                  <View key={i} style={[s.setDot, p.setsWon > i && { backgroundColor: COLORS[pi] }]} />
                ))}
              </View>
            )}

            {/* Dernier coup */}
            <View style={[s.strokeBox, p.lastStroke != null ? { backgroundColor: STROKES[p.lastStroke].color + '22' } : null]}>
              <Text style={s.strokeEmoji}>{p.lastStroke != null ? STROKES[p.lastStroke].emoji : '🏓'}</Text>
              <Text style={s.strokeName}>{p.lastStroke != null ? STROKES[p.lastStroke].name : 'En attente…'}</Text>
            </View>

            {/* Counts */}
            <View style={s.counts}>
              {STROKES.slice(0, 4).map((st, si) => (
                <View key={si} style={s.badge}>
                  <Text style={s.badgeEmoji}>{st.emoji}</Text>
                  <Text style={s.badgeLbl} numberOfLines={1}>{st.name}</Text>
                  <Text style={s.badgeVal}>{p.counts[si]}</Text>
                </View>
              ))}
            </View>

            {/* BLE + Contesté sur une ligne */}
            <View style={s.bleRow}>
              {!simulationMode && (
                p.reconnectMsg ? (
                  <View style={[s.reconnectBar, { flex: 1 }]}>
                    <Ionicons name="reload-outline" size={12} color="#f59e0b" />
                    <Text style={s.reconnectTxt}>{p.reconnectMsg}</Text>
                  </View>
                ) : (
                  <TouchableOpacity
                    style={[s.btnConnect, { flex: 1 }, p.connected && { borderColor: '#22c55e', backgroundColor: '#22c55e10' }]}
                    onPress={() => connectBLE(pi)} disabled={p.scanning}
                  >
                    <Ionicons name={p.connected ? 'bluetooth' : p.scanning ? 'radio-outline' : 'bluetooth-outline'}
                      size={14} color={p.connected ? '#22c55e' : p.scanning ? COLORS[pi] : '#475569'} />
                    <Text style={[s.btnConnectTxt, p.connected && { color: '#22c55e' }]} numberOfLines={1}>
                      {p.scanning ? 'Recherche…' : p.connected ? 'Connectée' : 'Connecter'}
                    </Text>
                  </TouchableOpacity>
                )
              )}
              <TouchableOpacity style={s.chalengeBtn} onPress={() => addChalenge(pi)} accessibilityRole="button" accessibilityLabel="Point contesté">
                <Ionicons name="alert-circle-outline" size={13} color="#f59e0b" />
                <Text style={s.chalengeTxt}>Contesté</Text>
              </TouchableOpacity>
            </View>

            {/* Point */}
            <TouchableOpacity
              style={[s.btnPoint, { backgroundColor: COLORS[pi] }]}
              onPress={() => addPoint(pi)}
              activeOpacity={0.8}
              accessibilityRole="button"
              accessibilityLabel={`Ajouter un point à ${p.name}`}
            >
              <Ionicons name="add" size={18} color="#fff" />
              <Text style={s.btnPointTxt}>+1 Point</Text>
            </TouchableOpacity>
          </View>
        ))}
      </View>

      {/* ── Modal Config ── */}
      <Modal visible={configVisible} transparent animationType="slide">
        <View style={s.overlay}>
          <View style={s.configModal}>
            <Text style={s.configTitle}>Configuration du match</Text>
            <Text style={s.configLabel}>Points pour gagner un set</Text>
            <View style={s.configRow}>
              {([11, 21] as const).map(v => (
                <TouchableOpacity key={v} style={[s.configOpt, pendingConfig.pointsToWin === v && s.configOptActive]}
                  onPress={() => setPendingConfig(c => ({ ...c, pointsToWin: v }))}>
                  <Text style={[s.configOptTxt, pendingConfig.pointsToWin === v && s.configOptTxtActive]}>{v} pts</Text>
                </TouchableOpacity>
              ))}
            </View>
            <Text style={s.configLabel}>Nombre de sets</Text>
            <View style={s.configRow}>
              {([1, 3, 5] as const).map(v => (
                <TouchableOpacity key={v} style={[s.configOpt, pendingConfig.numSets === v && s.configOptActive]}
                  onPress={() => setPendingConfig(c => ({ ...c, numSets: v }))}>
                  <Text style={[s.configOptTxt, pendingConfig.numSets === v && s.configOptTxtActive]}>
                    {v === 1 ? '1 set' : `Best of ${v}`}
                  </Text>
                </TouchableOpacity>
              ))}
            </View>
            {/* A4 – Simulation mode toggle */}
            <View style={s.simRow}>
              <Text style={s.configLabel}>Mode Simulation (sans BLE)</Text>
              <TouchableOpacity
                style={[s.simToggle, simulationMode && s.simToggleOn]}
                onPress={() => setSimulationMode(v => !v)}
              >
                <Text style={[s.simToggleTxt, simulationMode && { color: '#f59e0b' }]}>
                  {simulationMode ? 'ON' : 'OFF'}
                </Text>
              </TouchableOpacity>
            </View>
            <TouchableOpacity style={s.configApply} onPress={applyConfig}>
              <Text style={s.configApplyTxt}>Appliquer & Nouveau match</Text>
            </TouchableOpacity>
            <TouchableOpacity style={s.configCancel} onPress={() => setConfigVisible(false)}>
              <Text style={s.configCancelTxt}>Annuler</Text>
            </TouchableOpacity>
          </View>
        </View>
      </Modal>

      {/* ── Modal Profil Picker ── */}
      <Modal visible={profilePickerFor !== null} transparent animationType="slide">
        <View style={s.overlay}>
          <View style={s.configModal}>
            <Text style={s.configTitle}>Choisir un profil</Text>
            {profiles.length === 0 ? (
              <Text style={s.configLabel}>Aucun profil. Crée-en un dans l'onglet Profils.</Text>
            ) : (
              profiles.map(prof => (
                <TouchableOpacity key={prof.id} style={s.profileItem} onPress={async () => {
                  if (profilePickerFor === null) return;
                  const pi = profilePickerFor;
                  setPlayers(prev => {
                    const n = [...prev] as [PlayerState, PlayerState];
                    n[pi] = { ...n[pi], name: prof.name, profileId: prof.id };
                    return n;
                  });
                  setNames(prev => { const n = [...prev] as [string, string]; n[pi] = prof.name; return n; });
                  setProfilePickerFor(null);
                  const racket = await getRacketForPlayer(prof.id);
                  setRackets(prev => {
                    const n = [...prev] as [RacketInfo | null, RacketInfo | null];
                    n[pi] = racket;
                    return n;
                  });
                }}>
                  <Text style={s.profileItemName}>{prof.name}</Text>
                  <Text style={s.profileItemElo}>ELO {prof.elo}</Text>
                </TouchableOpacity>
              ))
            )}
            <TouchableOpacity style={s.configCancel} onPress={() => setProfilePickerFor(null)}>
              <Text style={s.configCancelTxt}>Annuler</Text>
            </TouchableOpacity>
          </View>
        </View>
      </Modal>

      {/* ── Modal Training ── */}
      <Modal visible={trainingVisible} transparent animationType="slide">
        <View style={s.overlay}>
          <View style={s.configModal}>
            <Text style={s.configTitle}>💪 Mode Entraînement</Text>

            <Text style={s.configLabel}>Coup cible</Text>
            <View style={s.configRow}>
              {STROKES.map((st, i) => (
                <TouchableOpacity key={i} style={[s.configOpt, trainingStroke === i && s.configOptActive]}
                  onPress={() => setTrainingStroke(i)}>
                  <Text style={s.strokeEmoji}>{st.emoji}</Text>
                  <Text style={[{ fontSize: 8, color: trainingStroke === i ? ACCENT : '#64748b', fontWeight: '700' }]}
                    numberOfLines={1}>{st.name}</Text>
                </TouchableOpacity>
              ))}
            </View>

            <Text style={s.configLabel}>Objectif de répétitions</Text>
            <View style={s.configRow}>
              {DRILL_TARGETS.map(t => (
                <TouchableOpacity key={t} style={[s.configOpt, trainingTarget === t && s.configOptActive]}
                  onPress={() => setTrainingTarget(t)}>
                  <Text style={[s.configOptTxt, trainingTarget === t && s.configOptTxtActive]}>{t}</Text>
                </TouchableOpacity>
              ))}
            </View>

            {/* Profile for training */}
            <Text style={s.configLabel}>Profil (optionnel)</Text>
            <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ maxHeight: 44 }}>
              <View style={{ flexDirection: 'row', gap: 6 }}>
                <TouchableOpacity style={[s.configOpt, trainingProfileFor === null && s.configOptActive, { paddingHorizontal: 10 }]}
                  onPress={() => setTrainingProfileFor(null)}>
                  <Text style={[s.configOptTxt, trainingProfileFor === null && s.configOptTxtActive]}>Aucun</Text>
                </TouchableOpacity>
                {profiles.map(p => (
                  <TouchableOpacity key={p.id} style={[s.configOpt, trainingProfileFor === p.id && s.configOptActive, { paddingHorizontal: 10 }]}
                    onPress={() => setTrainingProfileFor(p.id)}>
                    <Text style={[s.configOptTxt, trainingProfileFor === p.id && s.configOptTxtActive]}>{p.name}</Text>
                  </TouchableOpacity>
                ))}
              </View>
            </ScrollView>

            {trainingActive ? (
              <>
                {/* Active drill display */}
                <View style={s.drillActive}>
                  <Text style={s.drillEmoji}>{STROKES[trainingStroke].emoji}</Text>
                  <Text style={[s.drillCount, {
                    color: trainingCount >= trainingTarget ? '#4ade80' : STROKES[trainingStroke].color
                  }]}>
                    {trainingCount} / {trainingTarget}
                  </Text>
                  <Text style={s.drillTimer}>⏱ {fmtSecs(trainingTimer)}</Text>
                  {trainingCount >= trainingTarget && (
                    <Text style={s.drillDone}>🎉 Objectif atteint !</Text>
                  )}
                </View>
                <View style={{ flexDirection: 'row', gap: 8 }}>
                  <TouchableOpacity style={[s.configApply, { flex: 1, backgroundColor: '#22c55e' }]} onPress={stopTraining}>
                    <Text style={s.configApplyTxt}>Terminer</Text>
                  </TouchableOpacity>
                  <TouchableOpacity style={[s.configApply, { flex: 1, backgroundColor: '#475569' }]}
                    onPress={() => setTrainingCount(c => c + 1)}>
                    <Text style={s.configApplyTxt}>+1 Manuel</Text>
                  </TouchableOpacity>
                </View>
              </>
            ) : (
              <TouchableOpacity style={s.configApply} onPress={startTraining}>
                <Text style={s.configApplyTxt}>🚀 Démarrer le drill</Text>
              </TouchableOpacity>
            )}

            {!trainingActive && (
              <TouchableOpacity style={s.configCancel} onPress={() => setTrainingVisible(false)}>
                <Text style={s.configCancelTxt}>Annuler</Text>
              </TouchableOpacity>
            )}
          </View>
        </View>
      </Modal>

      {/* ── Modal Chalenges ── */}
      <Modal visible={showChalenge} transparent animationType="slide">
        <View style={s.overlay}>
          <View style={s.configModal}>
            <Text style={s.configTitle}>⚡ Points contestés</Text>
            {chalenges.length === 0 ? (
              <Text style={s.configLabel}>Aucun point contesté</Text>
            ) : (
              chalenges.map((ch, i) => (
                <View key={i} style={s.chalengeRow}>
                  <View style={[s.chalengeDot, { backgroundColor: COLORS[ch.pi] }]} />
                  <Text style={s.chalengeName}>{players[ch.pi].name}</Text>
                  <Text style={s.chalengeScore}>{ch.score}</Text>
                  <Text style={s.chalengeTime}>{ch.timestamp}</Text>
                </View>
              ))
            )}
            <TouchableOpacity style={s.configApply} onPress={() => setShowChalenge(false)}>
              <Text style={s.configApplyTxt}>Fermer</Text>
            </TouchableOpacity>
            {chalenges.length > 0 && (
              <TouchableOpacity style={s.configCancel} onPress={() => { setChalenges([]); setShowChalenge(false); }}>
                <Text style={s.configCancelTxt}>Effacer tout</Text>
              </TouchableOpacity>
            )}
          </View>
        </View>
      </Modal>

      {/* ── Badge Celebration ── */}
      {showBadgeCelebration && newBadges.length > 0 && (
        <BadgeCelebrationModal
          badges={newBadges}
          onClose={() => { setShowBadgeCelebration(false); setNewBadges([]); }}
        />
      )}

      {/* ── Share Stats Modal ── */}
      {showShare && shareProfile && (
        <Modal visible transparent animationType="fade">
          <StatShareCard profile={shareProfile} onClose={() => setShowShare(false)} />
        </Modal>
      )}

      {/* ── Modal gagnant ── */}
      <Modal visible={winner !== null} transparent animationType="fade">
        <View style={s.overlay}>
          <View style={[s.winCircle, { borderColor: winner !== null ? COLORS[winner] : COLORS[0] }]}>
            <Ionicons name="trophy" size={48} color={winner !== null ? COLORS[winner] : COLORS[0]} />
          </View>
          <Text style={s.winText}>{winner !== null ? players[winner].name : ''}</Text>
          <Text style={s.winSub}>remporte la victoire !</Text>
          <Text style={s.winScore}>
            {config.numSets > 1 ? `${p0.setsWon} – ${p1.setsWon} sets` : `${p0.score} – ${p1.score}`}
          </Text>
          <Text style={s.winTimer}>⏱ {fmtSecs(timerSecs)}</Text>

          {/* ELO delta */}
          {p0.profileId && p1.profileId && (() => {
            const pr0 = profiles.find(pr => pr.id === p0.profileId);
            const pr1 = profiles.find(pr => pr.id === p1.profileId);
            if (!pr0 || !pr1 || winner === null) return null;
            const [, , d1, d2] = newElos(pr0.elo, pr1.elo, winner as 0 | 1);
            return (
              <View style={s.eloRow}>
                <Text style={[s.eloDelta, { color: d1 >= 0 ? '#4ade80' : '#f87171' }]}>
                  {pr0.name} ELO {d1 >= 0 ? '+' : ''}{d1}
                </Text>
                <Text style={[s.eloDelta, { color: d2 >= 0 ? '#4ade80' : '#f87171' }]}>
                  {pr1.name} ELO {d2 >= 0 ? '+' : ''}{d2}
                </Text>
              </View>
            );
          })()}

          {/* Sets detail */}
          {sets.length > 1 && (
            <View style={s.setsDetail}>
              {sets.map((st, i) => (
                <View key={i} style={s.setDetailRow}>
                  <Text style={s.setDetailLbl}>Set {i + 1}</Text>
                  <Text style={s.setDetailScore}>{st.score1} – {st.score2}</Text>
                </View>
              ))}
            </View>
          )}

          {/* Stats rapides */}
          <View style={s.modalStats}>
            {[p0, p1].map((p, pi) => (
              <View key={pi} style={s.modalStatRow}>
                <View style={[s.dot, { backgroundColor: COLORS[pi] }]} />
                <Text style={[s.modalStatName, { color: COLORS[pi] }]} numberOfLines={1}>{p.name}</Text>
                <Text style={s.modalStatVal}>{p.counts.reduce((a, b) => a + b, 0)} coups</Text>
              </View>
            ))}
          </View>

          {/* Note */}
          <TextInput
            style={s.noteInput}
            value={matchNote}
            onChangeText={setMatchNote}
            placeholder="Ajouter une note… (optionnel)"
            placeholderTextColor="#334155"
            multiline maxLength={200}
          />

          <TouchableOpacity style={[s.btnReplay, { backgroundColor: ACCENT }]} onPress={handleSaveAndNew}>
            <Ionicons name="save-outline" size={18} color="#fff" />
            <Text style={s.btnReplayTxt}>Sauvegarder & Rejouer</Text>
          </TouchableOpacity>
          {winner !== null && players[winner]?.profileId && (() => {
            const winnerProf = profiles.find(pr => pr.id === players[winner!]?.profileId);
            if (!winnerProf) return null;
            return (
              <TouchableOpacity
                style={[s.btnReplay, { backgroundColor: '#0f172a', borderWidth: 1, borderColor: '#334155' }]}
                onPress={() => { setShareProfile(winnerProf); setShowShare(true); }}
              >
                <Ionicons name="share-outline" size={18} color="#94a3b8" />
                <Text style={[s.btnReplayTxt, { color: '#94a3b8' }]}>📤 Partager les stats</Text>
              </TouchableOpacity>
            );
          })()}
          <TouchableOpacity style={s.btnSkip} onPress={newGame}>
            <Text style={s.btnSkipTxt}>Rejouer sans sauvegarder</Text>
          </TouchableOpacity>
        </View>
      </Modal>
    </View>
  );
}

const s = StyleSheet.create({
  root: { flex: 1, backgroundColor: BG },

  // Top bar
  topBar: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
    paddingTop: 14, paddingHorizontal: 14, paddingBottom: 4,
  },
  setInfo: { flex: 1 },
  setInfoTxt: { fontSize: 11, color: '#475569', fontWeight: '600' },
  setsScore: { fontSize: 12, color: '#94a3b8', fontWeight: '800', marginTop: 1 },
  topActions: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  timerBox: {
    flexDirection: 'row', alignItems: 'center', gap: 3,
    backgroundColor: '#1e2d45', borderRadius: 8, paddingHorizontal: 7, paddingVertical: 4,
  },
  timerTxt: { fontSize: 12, color: '#64748b', fontWeight: '700', fontVariant: ['tabular-nums'] },
  topBtn: { padding: 6, borderRadius: 10, backgroundColor: '#1e2d45', borderWidth: 1, borderColor: '#2d3f5a' },

  // Coin flip
  coinFlipBanner: {
    backgroundColor: '#f59e0b20', borderWidth: 1, borderColor: '#f59e0b50',
    marginHorizontal: 14, borderRadius: 10, paddingVertical: 6, alignItems: 'center',
  },
  coinFlipTxt: { color: '#f59e0b', fontSize: 12, fontWeight: '700' },

  // ELO prediction
  eloPredRow: {
    flexDirection: 'row', justifyContent: 'center', gap: 10,
    marginHorizontal: 14, backgroundColor: '#1e2d45', borderRadius: 8,
    paddingVertical: 4, paddingHorizontal: 12, marginBottom: 2,
  },
  eloPredTxt: { fontSize: 11, fontWeight: '800' },
  eloPredSep: { color: '#334155', fontSize: 11 },

  // Score header
  scoreSec: { flexDirection: 'row', alignItems: 'center', paddingHorizontal: 14, paddingBottom: 4 },
  scorePlayerLabel: { flex: 1, flexDirection: 'row', alignItems: 'center', gap: 5 },
  scoreLabel: { fontSize: 12, fontWeight: '700', flexShrink: 1 },
  serveIndicator: { fontSize: 11 },
  dot: { width: 8, height: 8, borderRadius: 4, flexShrink: 0 },
  scoreCenter: { flexDirection: 'row', alignItems: 'center', gap: 10, paddingHorizontal: 6 },
  scoreNum: { fontSize: 58, fontWeight: '900', lineHeight: 66 },
  scoreSep: { fontSize: 28, color: '#334155', fontWeight: '300' },

  // Cards
  players: { flexDirection: 'row', gap: 8, paddingHorizontal: 8, paddingBottom: 8 },
  card: {
    flex: 1, backgroundColor: CARD_BG, borderRadius: 20, padding: 9, gap: 7,
    borderWidth: 2, borderColor: 'transparent',
  },
  profileRow: {
    flexDirection: 'row', alignItems: 'center', gap: 4,
    backgroundColor: '#0a0f1e', borderRadius: 8, paddingHorizontal: 7, paddingVertical: 4,
  },
  profileTxt: { flex: 1, fontSize: 10, color: '#475569', fontWeight: '600' },
  nameRow: { flexDirection: 'row', alignItems: 'center' },
  playerTag: { flexShrink: 1, borderWidth: 1, borderRadius: 8, paddingHorizontal: 7, paddingVertical: 3 },
  playerName: { fontSize: 10, fontWeight: '800', letterSpacing: 0.6, textTransform: 'uppercase' },
  nameEditRow: { flexDirection: 'row', alignItems: 'center', gap: 5 },
  nameInput: {
    flex: 1, borderWidth: 1.5, borderRadius: 8, paddingHorizontal: 7, paddingVertical: 3,
    color: '#f1f5f9', fontSize: 11, fontWeight: '700',
  },
  nameOkBtn: { borderRadius: 8, padding: 5 },
  setsRow: { flexDirection: 'row', gap: 4, justifyContent: 'center' },
  setDot: { width: 9, height: 9, borderRadius: 5, backgroundColor: '#1e2d45', borderWidth: 1, borderColor: '#2d3f5a' },
  strokeBox: { borderRadius: 10, paddingVertical: 8, alignItems: 'center', gap: 2, backgroundColor: '#0a0f1e' },
  strokeEmoji: { fontSize: 22, lineHeight: 26 },
  strokeName: { fontSize: 9, fontWeight: '600', color: '#64748b', textAlign: 'center' },
  counts: { flexDirection: 'row', flexWrap: 'wrap', gap: 3 },
  badge: {
    width: '47%', flexDirection: 'row', alignItems: 'center', gap: 2,
    backgroundColor: '#0a0f1e', borderRadius: 6, paddingHorizontal: 4, paddingVertical: 3,
  },
  badgeEmoji: { fontSize: 10 },
  badgeLbl: { flex: 1, fontSize: 8, color: '#94a3b8' },
  badgeVal: { fontSize: 11, fontWeight: '800', color: '#f1f5f9', minWidth: 12, textAlign: 'right' },
  reconnectBar: {
    flexDirection: 'row', alignItems: 'center', gap: 5,
    backgroundColor: '#f59e0b10', borderWidth: 1, borderColor: '#f59e0b40',
    borderRadius: 9, paddingHorizontal: 7, paddingVertical: 7,
  },
  reconnectTxt: { fontSize: 10, color: '#f59e0b', fontWeight: '600' },
  btnConnect: {
    flexDirection: 'row', alignItems: 'center', gap: 5,
    borderWidth: 1.5, borderColor: '#1e2d45', borderRadius: 9, paddingHorizontal: 7, paddingVertical: 7,
  },
  btnConnectTxt: { flex: 1, fontSize: 10, fontWeight: '600', color: '#94a3b8' },
  btnPoint: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center',
    borderRadius: 11, paddingVertical: 10, gap: 3,
  },
  btnPointTxt: { color: '#fff', fontSize: 13, fontWeight: '800' },

  // Config modal
  overlay: {
    flex: 1, backgroundColor: 'rgba(0,0,0,0.9)',
    alignItems: 'center', justifyContent: 'center', padding: 20,
  },
  configModal: {
    width: '100%', backgroundColor: CARD_BG, borderRadius: 24,
    padding: 22, gap: 10, borderWidth: 1, borderColor: '#1e2d45',
    maxHeight: '90%',
  },
  configTitle: { fontSize: 17, fontWeight: '900', color: '#f1f5f9', textAlign: 'center', marginBottom: 2 },
  configLabel: { fontSize: 11, color: '#64748b', fontWeight: '600', textTransform: 'uppercase', letterSpacing: 0.5 },
  configRow: { flexDirection: 'row', gap: 6, flexWrap: 'wrap' },
  configOpt: {
    flex: 1, minWidth: 50, paddingVertical: 9, borderRadius: 10,
    borderWidth: 1.5, borderColor: '#1e2d45', alignItems: 'center',
  },
  configOptActive: { borderColor: ACCENT, backgroundColor: ACCENT + '15' },
  configOptTxt: { fontSize: 12, color: '#64748b', fontWeight: '700' },
  configOptTxtActive: { color: ACCENT },
  configApply: {
    backgroundColor: ACCENT, borderRadius: 13, paddingVertical: 13, alignItems: 'center', marginTop: 2,
  },
  configApplyTxt: { color: '#fff', fontSize: 13, fontWeight: '800' },
  configCancel: { alignItems: 'center', paddingVertical: 4 },
  configCancelTxt: { color: '#475569', fontSize: 12, textDecorationLine: 'underline' },

  // Profile picker items
  profileItem: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
    backgroundColor: '#0a0f1e', borderRadius: 11, paddingHorizontal: 13, paddingVertical: 11,
  },
  profileItemName: { fontSize: 14, color: '#f1f5f9', fontWeight: '700' },
  profileItemElo: { fontSize: 12, color: '#64748b' },

  // Training
  drillActive: { alignItems: 'center', gap: 4, paddingVertical: 10 },
  drillEmoji: { fontSize: 32 },
  drillCount: { fontSize: 36, fontWeight: '900' },
  drillTimer: { fontSize: 13, color: '#64748b' },
  drillDone: { fontSize: 16, fontWeight: '800', color: '#4ade80' },

  // Winner modal
  winCircle: {
    width: 90, height: 90, borderRadius: 45, borderWidth: 3,
    alignItems: 'center', justifyContent: 'center', backgroundColor: 'rgba(255,255,255,0.05)',
  },
  winText: { fontSize: 26, fontWeight: '900', color: '#f1f5f9', textAlign: 'center' },
  winSub: { fontSize: 14, color: '#64748b' },
  winScore: { fontSize: 32, fontWeight: '900', color: '#f1f5f9' },
  winTimer: { fontSize: 12, color: '#475569' },
  eloRow: { gap: 2, alignItems: 'center' },
  eloDelta: { fontSize: 12, fontWeight: '700' },
  setsDetail: { flexDirection: 'row', gap: 8, flexWrap: 'wrap', justifyContent: 'center' },
  setDetailRow: {
    backgroundColor: '#1e2d45', borderRadius: 8, paddingHorizontal: 10, paddingVertical: 4,
    alignItems: 'center',
  },
  setDetailLbl: { fontSize: 9, color: '#475569', fontWeight: '700' },
  setDetailScore: { fontSize: 13, fontWeight: '900', color: '#f1f5f9' },
  modalStats: { width: '100%', gap: 6 },
  modalStatRow: {
    flexDirection: 'row', alignItems: 'center', gap: 7,
    backgroundColor: CARD_BG, borderRadius: 11, paddingHorizontal: 12, paddingVertical: 9,
  },
  modalStatName: { flex: 1, fontSize: 13, fontWeight: '700' },
  modalStatVal: { fontSize: 12, color: '#64748b', fontWeight: '600' },
  noteInput: {
    width: '100%', borderWidth: 1, borderColor: '#1e2d45', borderRadius: 12,
    paddingHorizontal: 12, paddingVertical: 10, color: '#94a3b8', fontSize: 12,
    backgroundColor: '#0a0f1e10', minHeight: 44,
  },
  btnReplay: {
    flexDirection: 'row', alignItems: 'center', gap: 7,
    borderRadius: 14, paddingHorizontal: 24, paddingVertical: 13,
    width: '100%', justifyContent: 'center',
  },
  btnReplayTxt: { color: '#fff', fontSize: 14, fontWeight: '700' },
  btnSkip: { paddingVertical: 6 },
  btnSkipTxt: { color: '#475569', fontSize: 12, textDecorationLine: 'underline' },

  // Chalenge
  chalengeBtn: {
    flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 4,
    borderWidth: 1, borderColor: '#f59e0b40', backgroundColor: '#f59e0b10',
    borderRadius: 9, paddingVertical: 6,
  },
  chalengeTxt: { fontSize: 10, fontWeight: '700', color: '#f59e0b' },
  chalengeRow: { flexDirection: 'row', alignItems: 'center', gap: 8, paddingVertical: 6, borderBottomWidth: 1, borderBottomColor: '#1e2d45' },
  chalengeDot: { width: 8, height: 8, borderRadius: 4 },
  chalengeName: { flex: 1, fontSize: 12, color: '#f1f5f9', fontWeight: '700' },
  chalengeScore: { fontSize: 12, color: '#64748b' },
  chalengeTime: { fontSize: 10, color: '#334155' },

  // DEUCE / AVT
  deuceBanner: {
    marginHorizontal: 14, borderRadius: 10, paddingVertical: 6, alignItems: 'center',
    backgroundColor: '#6366f120', borderWidth: 1, borderColor: '#6366f150',
  },
  deuceTxt: { color: '#6366f1', fontSize: 12, fontWeight: '900', letterSpacing: 1.5 },

  // Raquette
  racketRow: { flexDirection: 'row', alignItems: 'center', gap: 5, paddingHorizontal: 2, marginTop: -4 },
  racketTxt: { fontSize: 10, fontWeight: '700', opacity: 0.85 },

  // A1 – Service banner
  serviceBanner: {
    position: 'absolute', top: 80, left: 0, right: 0, zIndex: 50,
    alignItems: 'center',
  },
  serviceBannerTxt: {
    backgroundColor: '#6366f1ee', color: '#fff', fontSize: 13, fontWeight: '800',
    paddingHorizontal: 18, paddingVertical: 8, borderRadius: 20,
  },

  // A3 – Streak overlay
  streakOverlay: {
    position: 'absolute', bottom: 120, left: 0, right: 0, zIndex: 60,
    alignItems: 'center',
  },
  streakOverlayTxt: {
    backgroundColor: '#f97316ee', color: '#fff', fontSize: 16, fontWeight: '900',
    paddingHorizontal: 20, paddingVertical: 10, borderRadius: 20,
  },

  // A4 – Simulation banner & toggle
  simBanner: {
    flexDirection: 'row', alignItems: 'center', gap: 6,
    marginHorizontal: 14, marginBottom: 4,
    backgroundColor: '#f59e0b10', borderWidth: 1, borderColor: '#f59e0b40',
    borderRadius: 10, paddingHorizontal: 12, paddingVertical: 6,
  },
  simBannerTxt: { flex: 1, fontSize: 11, color: '#f59e0b', fontWeight: '600' },
  simRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  simToggle: {
    paddingHorizontal: 14, paddingVertical: 6, borderRadius: 10,
    borderWidth: 1.5, borderColor: '#1e2d45', backgroundColor: '#0a0f1e',
  },
  simToggleOn: { borderColor: '#f59e0b', backgroundColor: '#f59e0b15' },
  simToggleTxt: { fontSize: 12, fontWeight: '800', color: '#475569' },

  // A5 – Momentum chart
  momentumSection: {
    marginHorizontal: 14, marginBottom: 4,
    backgroundColor: CARD_BG, borderRadius: 12, padding: 10,
    borderWidth: 1, borderColor: '#1e2d45', gap: 6,
  },
  momentumHeader: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  momentumTitle: { flex: 1, fontSize: 11, color: '#64748b', fontWeight: '700', textTransform: 'uppercase', letterSpacing: 0.5 },

  // BLE + Contesté row
  bleRow: { flexDirection: 'row', alignItems: 'center', gap: 6 },
});
