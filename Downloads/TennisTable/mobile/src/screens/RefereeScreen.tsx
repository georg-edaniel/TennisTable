import React, { useRef, useState } from 'react';
import {
  Alert, Animated, ScrollView, StyleSheet, Text, TextInput,
  TouchableOpacity, View,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import * as Haptics from 'expo-haptics';
import * as Print from 'expo-print';
import * as Sharing from 'expo-sharing';
import { saveMatch } from '../storage/matchStorage';
import { countsToStrokes, BG, CARD_BG } from '../types';

const ACCENT = '#6366f1';
const C1 = '#6366f1';
const C2 = '#f43f5e';

function fmtSecs(s: number): string {
  const m = Math.floor(s / 60);
  return `${m}:${String(s % 60).padStart(2, '0')}`;
}

type Cards = { yellow: [number, number]; red: [number, number] };

export default function RefereeScreen() {
  const [name1, setName1] = useState('Joueur A');
  const [name2, setName2] = useState('Joueur B');
  const [score1, setScore1] = useState(0);
  const [score2, setScore2] = useState(0);
  const [timer, setTimer] = useState(0);
  const [timerRunning, setTimerRunning] = useState(false);
  const [matchStarted, setMatchStarted] = useState(false);
  const [winner, setWinner] = useState<0 | 1 | null>(null);
  const [disqualified, setDisqualified] = useState<0 | 1 | null>(null);
  const [saved, setSaved] = useState(false);
  const [pointsToWin, setPointsToWin] = useState<11 | 21>(11);
  const [cards, setCards] = useState<Cards>({ yellow: [0, 0], red: [0, 0] });

  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const startTimeRef = useRef(Date.now());
  const historyRef = useRef<{ s1: number; s2: number }[]>([]);
  const scaleAnim1 = useRef(new Animated.Value(1)).current;
  const scaleAnim2 = useRef(new Animated.Value(1)).current;

  function startTimer() {
    if (timerRunning) return;
    setTimerRunning(true);
    startTimeRef.current = Date.now() - timer * 1000;
    timerRef.current = setInterval(() => {
      setTimer(Math.floor((Date.now() - startTimeRef.current) / 1000));
    }, 1000);
  }

  function stopTimer() {
    setTimerRunning(false);
    if (timerRef.current) clearInterval(timerRef.current);
  }

  function pulse(anim: Animated.Value) {
    Animated.sequence([
      Animated.timing(anim, { toValue: 1.35, duration: 70, useNativeDriver: true }),
      Animated.timing(anim, { toValue: 1, duration: 100, useNativeDriver: true }),
    ]).start();
  }

  function addPoint(pi: 0 | 1) {
    if (winner !== null) return;
    historyRef.current.push({ s1: score1, s2: score2 });

    if (!matchStarted) {
      setMatchStarted(true);
      startTimer();
    }

    const newS1 = pi === 0 ? score1 + 1 : score1;
    const newS2 = pi === 1 ? score2 + 1 : score2;

    setScore1(newS1);
    setScore2(newS2);

    if (pi === 0) pulse(scaleAnim1);
    else pulse(scaleAnim2);

    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium).catch(() => {});

    const winner_ = checkWinner(newS1, newS2);
    if (winner_ !== null) {
      setWinner(winner_);
      stopTimer();
      Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success).catch(() => {});
    }
  }

  function checkWinner(s1: number, s2: number): 0 | 1 | null {
    const pts = pointsToWin;
    if (s1 >= pts && (s1 - s2) >= 2) return 0;
    if (s2 >= pts && (s2 - s1) >= 2) return 1;
    return null;
  }

  function undo() {
    if (historyRef.current.length === 0) return;
    const last = historyRef.current.pop()!;
    setScore1(last.s1);
    setScore2(last.s2);
    setWinner(null);
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light).catch(() => {});
  }

  function reset() {
    Alert.alert('Réinitialiser', 'Nouveau match ?', [
      { text: 'Annuler', style: 'cancel' },
      {
        text: 'Oui', onPress: () => {
          stopTimer();
          setScore1(0); setScore2(0);
          setTimer(0); setTimerRunning(false);
          setWinner(null); setDisqualified(null);
          setMatchStarted(false); setSaved(false);
          setCards({ yellow: [0, 0], red: [0, 0] });
          historyRef.current = [];
        },
      },
    ]);
  }

  function giveCard(pi: 0 | 1, type: 'yellow' | 'red') {
    if (winner !== null) return;
    if (type === 'red') {
      Alert.alert(
        '🟥 Carton rouge',
        `Disqualifier ${pi === 0 ? name1 : name2} ?`,
        [
          { text: 'Annuler', style: 'cancel' },
          {
            text: 'Disqualifier', style: 'destructive',
            onPress: () => {
              setCards(prev => {
                const red = [...prev.red] as [number, number];
                red[pi]++;
                return { ...prev, red };
              });
              const w = pi === 0 ? 1 : 0;
              setDisqualified(pi);
              setWinner(w as 0 | 1);
              stopTimer();
              Haptics.notificationAsync(Haptics.NotificationFeedbackType.Error).catch(() => {});
            },
          },
        ]
      );
    } else {
      setCards(prev => {
        const yellow = [...prev.yellow] as [number, number];
        yellow[pi]++;
        return { ...prev, yellow };
      });
      Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Heavy).catch(() => {});
    }
  }

  async function handleSave() {
    if (winner === null || saved) return;
    try {
      const emptyStrokes = countsToStrokes([0, 0, 0, 0, 0]);
      const note = disqualified !== null
        ? `⚖️ Arbitré — 🟥 Disqualification ${disqualified === 0 ? name1 : name2}`
        : `⚖️ Arbitré — 🟨×${cards.yellow[0]}/${cards.yellow[1]}`;
      await saveMatch({
        id: Date.now().toString(),
        date: new Date().toISOString(),
        player1: name1, player2: name2,
        score1, score2,
        winner,
        durationSecs: timer,
        strokes1: emptyStrokes, strokes2: emptyStrokes,
        config: { pointsToWin, numSets: 1 },
        note,
      });
      setSaved(true);
      Alert.alert('✅', 'Match sauvegardé !');
    } catch (e: any) {
      Alert.alert('Erreur', e.message ?? 'Impossible de sauvegarder');
    }
  }

  async function handleExportPDF() {
    try {
      const cardRows = [name1, name2].map((name, i) => `
        <tr>
          <td>${name}</td>
          <td>${i === 0 ? score1 : score2}</td>
          <td style="color:#f59e0b">${cards.yellow[i]}</td>
          <td style="color:#ef4444">${cards.red[i]}</td>
          <td>${disqualified === i ? '🟥 DQ' : winner === i ? '🏆' : ''}</td>
        </tr>
      `).join('');

      const html = `<!DOCTYPE html>
<html><head><meta charset="utf-8"/>
<style>
* { font-family: Arial, sans-serif; margin: 0; padding: 0; box-sizing: border-box; }
body { background: #fff; padding: 32px; }
h1 { font-size: 22px; color: #1e293b; margin-bottom: 4px; }
.sub { color: #64748b; font-size: 13px; margin-bottom: 24px; }
table { width: 100%; border-collapse: collapse; }
th { background: #f1f5f9; color: #334155; font-size: 12px; padding: 10px; text-align: left; }
td { padding: 10px; border-bottom: 1px solid #e2e8f0; font-size: 14px; }
.footer { margin-top: 32px; font-size: 11px; color: #94a3b8; text-align: center; }
</style></head>
<body>
<h1>⚖️ Feuille de match arbitré</h1>
<p class="sub">Durée : ${fmtSecs(timer)} · ${new Date().toLocaleString('fr-FR')}</p>
<table>
  <tr>
    <th>Joueur</th><th>Score</th><th>🟨 Avert.</th><th>🟥 Cartons</th><th>Résultat</th>
  </tr>
  ${cardRows}
</table>
<div class="footer">Généré par TT Tracker v5.0</div>
</body></html>`;

      const { uri } = await Print.printToFileAsync({ html, width: 595, height: 842 });
      if (await Sharing.isAvailableAsync()) {
        await Sharing.shareAsync(uri, { mimeType: 'application/pdf', dialogTitle: 'Feuille de match' });
      } else {
        Alert.alert('PDF créé', uri);
      }
    } catch (e: any) {
      Alert.alert('Erreur', e.message ?? 'Génération PDF échouée');
    }
  }

  const isDeuce = score1 >= pointsToWin - 1 && score2 >= pointsToWin - 1 && score1 === score2;
  const hasAdvantage = score1 >= pointsToWin - 1 && score2 >= pointsToWin - 1 && Math.abs(score1 - score2) === 1;

  return (
    <ScrollView style={s.root} contentContainerStyle={s.content} showsVerticalScrollIndicator={false}>
      <View style={s.header}>
        <Text style={s.title}>⚖️ Arbitre</Text>
        <Text style={s.subtitle}>Interface d'arbitrage sans BLE</Text>
      </View>

      {/* Config */}
      {!matchStarted && (
        <View style={s.configCard}>
          <Text style={s.configLabel}>Jeu en :</Text>
          <View style={s.configRow}>
            {([11, 21] as const).map(n => (
              <TouchableOpacity
                key={n}
                style={[s.cfgBtn, pointsToWin === n && s.cfgBtnActive]}
                onPress={() => setPointsToWin(n)}
              >
                <Text style={[s.cfgTxt, pointsToWin === n && s.cfgTxtActive]}>{n} pts</Text>
              </TouchableOpacity>
            ))}
          </View>
        </View>
      )}

      {/* Noms */}
      <View style={s.namesRow}>
        <TextInput
          style={[s.nameInput, { borderColor: C1 + '50' }]}
          value={name1} onChangeText={setName1}
          editable={!matchStarted}
          placeholder="Joueur A" placeholderTextColor="#475569" maxLength={14}
        />
        <Text style={s.vsText}>vs</Text>
        <TextInput
          style={[s.nameInput, { borderColor: C2 + '50' }]}
          value={name2} onChangeText={setName2}
          editable={!matchStarted}
          placeholder="Joueur B" placeholderTextColor="#475569" maxLength={14}
        />
      </View>

      {/* Timer */}
      <View style={s.timerRow}>
        <Ionicons name="time-outline" size={14} color="#64748b" />
        <Text style={s.timerTxt}>{fmtSecs(timer)}</Text>
        {isDeuce && <Text style={s.statusBadge}>ÉGALITÉ</Text>}
        {hasAdvantage && (
          <Text style={[s.statusBadge, { backgroundColor: '#f59e0b20', borderColor: '#f59e0b50', color: '#f59e0b' }]}>
            AVT. {score1 > score2 ? name1 : name2}
          </Text>
        )}
      </View>

      {/* Score + zones tactiles */}
      {winner === null ? (
        <View style={s.scoreRow}>
          <TouchableOpacity
            style={[s.scoreZone, { backgroundColor: C1 + '18', borderColor: C1 + '40' }]}
            onPress={() => addPoint(0)} activeOpacity={0.75}
          >
            <Text style={s.zoneName} numberOfLines={1}>{name1}</Text>
            <Animated.Text style={[s.scoreNum, { color: C1, transform: [{ scale: scaleAnim1 }] }]}>
              {score1}
            </Animated.Text>
            {/* Cards */}
            <View style={s.cardBadgeRow}>
              {cards.yellow[0] > 0 && <Text style={s.yellowBadge}>🟨×{cards.yellow[0]}</Text>}
              {cards.red[0] > 0 && <Text style={s.redBadge}>🟥×{cards.red[0]}</Text>}
            </View>
            <Text style={s.tapHint}>Tap = +1 point</Text>
          </TouchableOpacity>

          <View style={s.midCol}>
            <Text style={s.dash}>–</Text>
            <TouchableOpacity style={s.undoBtn} onPress={undo}>
              <Ionicons name="arrow-undo" size={16} color="#64748b" />
            </TouchableOpacity>
          </View>

          <TouchableOpacity
            style={[s.scoreZone, { backgroundColor: C2 + '18', borderColor: C2 + '40' }]}
            onPress={() => addPoint(1)} activeOpacity={0.75}
          >
            <Text style={s.zoneName} numberOfLines={1}>{name2}</Text>
            <Animated.Text style={[s.scoreNum, { color: C2, transform: [{ scale: scaleAnim2 }] }]}>
              {score2}
            </Animated.Text>
            <View style={s.cardBadgeRow}>
              {cards.yellow[1] > 0 && <Text style={s.yellowBadge}>🟨×{cards.yellow[1]}</Text>}
              {cards.red[1] > 0 && <Text style={s.redBadge}>🟥×{cards.red[1]}</Text>}
            </View>
            <Text style={s.tapHint}>Tap = +1 point</Text>
          </TouchableOpacity>
        </View>
      ) : (
        <View style={[s.winnerBox, { borderColor: winner === 0 ? C1 : C2 }]}>
          <Text style={s.winnerEmoji}>{disqualified !== null ? '🚫' : '🏆'}</Text>
          <Text style={[s.winnerName, { color: winner === 0 ? C1 : C2 }]}>
            {winner === 0 ? name1 : name2}
          </Text>
          {disqualified !== null && (
            <Text style={s.disqTxt}>
              🟥 {disqualified === 0 ? name1 : name2} disqualifié(e)
            </Text>
          )}
          <Text style={s.winnerScore}>{score1} – {score2}</Text>
          <Text style={s.winnerDur}>Durée : {fmtSecs(timer)}</Text>
          {/* Cards summary */}
          {(cards.yellow[0] > 0 || cards.yellow[1] > 0 || cards.red[0] > 0 || cards.red[1] > 0) && (
            <View style={s.cardSummary}>
              <Text style={s.cardSumTxt}>
                🟨 {name1}: {cards.yellow[0]} · {name2}: {cards.yellow[1]}
              </Text>
              {(cards.red[0] > 0 || cards.red[1] > 0) && (
                <Text style={s.cardSumTxt}>
                  🟥 {name1}: {cards.red[0]} · {name2}: {cards.red[1]}
                </Text>
              )}
            </View>
          )}
        </View>
      )}

      {/* Card buttons (always visible during match) */}
      {winner === null && matchStarted && (
        <View style={s.cardRow}>
          <Text style={s.cardRowLabel}>Cartons :</Text>
          {([0, 1] as const).map(pi => (
            <View key={pi} style={s.cardPlayerGroup}>
              <Text style={[s.cardPlayerName, { color: pi === 0 ? C1 : C2 }]} numberOfLines={1}>
                {pi === 0 ? name1 : name2}
              </Text>
              <View style={{ flexDirection: 'row', gap: 6 }}>
                <TouchableOpacity style={s.yellowBtn} onPress={() => giveCard(pi, 'yellow')}>
                  <Text style={s.cardBtnTxt}>🟨</Text>
                </TouchableOpacity>
                <TouchableOpacity style={s.redBtn} onPress={() => giveCard(pi, 'red')}>
                  <Text style={s.cardBtnTxt}>🟥</Text>
                </TouchableOpacity>
              </View>
            </View>
          ))}
        </View>
      )}

      {/* Actions */}
      <View style={s.actionsRow}>
        <TouchableOpacity style={s.resetBtn} onPress={reset}>
          <Ionicons name="refresh" size={16} color="#94a3b8" />
          <Text style={s.resetTxt}>Réinitialiser</Text>
        </TouchableOpacity>

        {winner !== null && !saved && (
          <TouchableOpacity style={s.saveBtn} onPress={handleSave}>
            <Ionicons name="save-outline" size={16} color="#fff" />
            <Text style={s.saveTxt}>Sauvegarder</Text>
          </TouchableOpacity>
        )}
        {saved && (
          <View style={s.savedBadge}>
            <Ionicons name="checkmark-circle" size={16} color="#4ade80" />
            <Text style={s.savedTxt}>Sauvegardé</Text>
          </View>
        )}
      </View>

      {/* PDF export (visible after match end) */}
      {winner !== null && (
        <TouchableOpacity style={s.pdfBtn} onPress={handleExportPDF}>
          <Ionicons name="document-text-outline" size={16} color="#6366f1" />
          <Text style={s.pdfTxt}>📄 Feuille de match PDF</Text>
        </TouchableOpacity>
      )}

      <View style={{ height: 32 }} />
    </ScrollView>
  );
}

const s = StyleSheet.create({
  root: { flex: 1, backgroundColor: BG },
  content: { padding: 20, paddingTop: 50, gap: 16 },
  header: { gap: 4 },
  title: { fontSize: 26, fontWeight: '900', color: '#f1f5f9' },
  subtitle: { fontSize: 13, color: '#475569' },

  configCard: {
    backgroundColor: CARD_BG, borderRadius: 16, padding: 14,
    borderWidth: 1, borderColor: '#1e2d45', gap: 10,
  },
  configLabel: { fontSize: 13, color: '#94a3b8', fontWeight: '700' },
  configRow: { flexDirection: 'row', gap: 10 },
  cfgBtn: {
    flex: 1, paddingVertical: 10, borderRadius: 12, alignItems: 'center',
    borderWidth: 1.5, borderColor: '#1e2d45', backgroundColor: '#0a0f1e',
  },
  cfgBtnActive: { borderColor: ACCENT, backgroundColor: ACCENT + '20' },
  cfgTxt: { fontSize: 14, fontWeight: '700', color: '#475569' },
  cfgTxtActive: { color: ACCENT },

  namesRow: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  nameInput: {
    flex: 1, backgroundColor: CARD_BG, borderWidth: 1.5, borderRadius: 12,
    paddingHorizontal: 12, paddingVertical: 10, color: '#f1f5f9',
    fontSize: 14, fontWeight: '700', textAlign: 'center',
  },
  vsText: { fontSize: 14, color: '#475569', fontWeight: '700' },

  timerRow: { flexDirection: 'row', alignItems: 'center', gap: 8, justifyContent: 'center' },
  timerTxt: { fontSize: 18, color: '#94a3b8', fontWeight: '700' },
  statusBadge: {
    fontSize: 10, fontWeight: '800', color: '#6366f1',
    backgroundColor: '#6366f120', borderWidth: 1, borderColor: '#6366f140',
    borderRadius: 6, paddingHorizontal: 7, paddingVertical: 3, letterSpacing: 0.5,
  },

  scoreRow: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  scoreZone: {
    flex: 1, alignItems: 'center', justifyContent: 'center', gap: 6,
    borderWidth: 1.5, borderRadius: 20, paddingVertical: 28,
    minHeight: 160,
  },
  zoneName: { fontSize: 14, fontWeight: '800', color: '#f1f5f9' },
  scoreNum: { fontSize: 72, fontWeight: '900', lineHeight: 82 },
  tapHint: { fontSize: 10, color: '#475569', fontStyle: 'italic' },
  cardBadgeRow: { flexDirection: 'row', gap: 4 },
  yellowBadge: { fontSize: 11, color: '#f59e0b', fontWeight: '700' },
  redBadge: { fontSize: 11, color: '#ef4444', fontWeight: '700' },

  midCol: { alignItems: 'center', gap: 12 },
  dash: { fontSize: 24, color: '#1e2d45', fontWeight: '300' },
  undoBtn: {
    width: 38, height: 38, borderRadius: 19,
    backgroundColor: '#1e2d45', alignItems: 'center', justifyContent: 'center',
  },

  // Card buttons
  cardRow: {
    flexDirection: 'row', alignItems: 'center', gap: 10, flexWrap: 'wrap',
    backgroundColor: CARD_BG, borderRadius: 14, padding: 12, borderWidth: 1, borderColor: '#1e2d45',
  },
  cardRowLabel: { fontSize: 12, color: '#64748b', fontWeight: '700', width: '100%' },
  cardPlayerGroup: { flex: 1, gap: 6, alignItems: 'center' },
  cardPlayerName: { fontSize: 12, fontWeight: '800' },
  yellowBtn: {
    paddingHorizontal: 14, paddingVertical: 8, borderRadius: 10,
    backgroundColor: '#f59e0b20', borderWidth: 1, borderColor: '#f59e0b50',
  },
  redBtn: {
    paddingHorizontal: 14, paddingVertical: 8, borderRadius: 10,
    backgroundColor: '#ef444420', borderWidth: 1, borderColor: '#ef444450',
  },
  cardBtnTxt: { fontSize: 16 },

  winnerBox: {
    backgroundColor: CARD_BG, borderRadius: 20, padding: 28, alignItems: 'center',
    gap: 8, borderWidth: 2,
  },
  winnerEmoji: { fontSize: 40 },
  winnerName: { fontSize: 28, fontWeight: '900' },
  winnerScore: { fontSize: 20, fontWeight: '800', color: '#f1f5f9' },
  winnerDur: { fontSize: 13, color: '#475569' },
  disqTxt: { fontSize: 13, color: '#ef4444', fontWeight: '700' },
  cardSummary: { gap: 2, alignItems: 'center' },
  cardSumTxt: { fontSize: 12, color: '#64748b' },

  actionsRow: { flexDirection: 'row', gap: 10, justifyContent: 'center' },
  resetBtn: {
    flexDirection: 'row', alignItems: 'center', gap: 6,
    paddingHorizontal: 16, paddingVertical: 10, borderRadius: 12,
    backgroundColor: '#1e2d45',
  },
  resetTxt: { color: '#94a3b8', fontSize: 13, fontWeight: '700' },
  saveBtn: {
    flexDirection: 'row', alignItems: 'center', gap: 6,
    paddingHorizontal: 20, paddingVertical: 10, borderRadius: 12,
    backgroundColor: ACCENT,
  },
  saveTxt: { color: '#fff', fontSize: 13, fontWeight: '700' },
  savedBadge: {
    flexDirection: 'row', alignItems: 'center', gap: 6,
    paddingHorizontal: 16, paddingVertical: 10, borderRadius: 12,
    backgroundColor: '#4ade8015',
  },
  savedTxt: { color: '#4ade80', fontSize: 13, fontWeight: '700' },
  pdfBtn: {
    flexDirection: 'row', alignItems: 'center', gap: 8, justifyContent: 'center',
    paddingVertical: 12, borderRadius: 12,
    backgroundColor: ACCENT + '15', borderWidth: 1, borderColor: ACCENT + '40',
  },
  pdfTxt: { color: ACCENT, fontSize: 13, fontWeight: '700' },
});
