import React, { useCallback, useState } from 'react';
import { ActivityIndicator, Modal, ScrollView, StyleSheet, Text, TouchableOpacity, View } from 'react-native';
import { useFocusEffect, useNavigation } from '@react-navigation/native';
import { BottomTabNavigationProp } from '@react-navigation/bottom-tabs';
import EmptyState from '../components/EmptyState';
import StatShareCard from '../components/StatShareCard';
import { TabParams } from '../navigation/AppNavigator';
import { useLoadingData } from '../hooks/useLoadingData';
import { Ionicons } from '@expo/vector-icons';
import { loadMatches } from '../storage/matchStorage';
import { loadProfiles } from '../storage/profileStorage';
import {
  BG, CARD_BG, COLORS, MatchRecord, PlayerProfile,
  STROKES, StrokeCounts, favoriteStroke,
} from '../types';
import { DEFAULT_ELO } from '../services/eloService';
import { generateTips, detectFatigue } from '../services/tipService';

const ACCENT = '#6366f1';
type Period = 'today' | 'week' | 'month' | 'all';

function sumStrokes(matches: MatchRecord[], side: 'strokes1' | 'strokes2'): StrokeCounts {
  return matches.reduce((acc, m) => {
    const s = m[side];
    return { bhDrive: acc.bhDrive + s.bhDrive, bhSmash: acc.bhSmash + s.bhSmash, fhDrive: acc.fhDrive + s.fhDrive, fhLoop: acc.fhLoop + s.fhLoop, fhSmash: acc.fhSmash + s.fhSmash };
  }, { bhDrive: 0, bhSmash: 0, fhDrive: 0, fhLoop: 0, fhSmash: 0 });
}

function toArr(s: StrokeCounts): number[] {
  return [s.bhDrive, s.bhSmash, s.fhDrive, s.fhLoop, s.fhSmash];
}

function totalOf(s: StrokeCounts): number {
  return s.bhDrive + s.bhSmash + s.fhDrive + s.fhLoop + s.fhSmash;
}

function WinBar({ wins, total, color, name }: { wins: number; total: number; color: string; name: string }) {
  const pct = total > 0 ? (wins / total) * 100 : 0;
  return (
    <View style={wb.row}>
      <Text style={[wb.name, { color }]} numberOfLines={1}>{name}</Text>
      <View style={wb.track}><View style={[wb.fill, { width: `${pct}%` as any, backgroundColor: color }]} /></View>
      <Text style={[wb.pct, { color }]}>{Math.round(pct)}%</Text>
      <Text style={wb.count}>{wins}V</Text>
    </View>
  );
}
const wb = StyleSheet.create({
  row: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  name: { width: 90, fontSize: 13, fontWeight: '700' },
  track: { flex: 1, height: 10, backgroundColor: '#1e2d45', borderRadius: 5, overflow: 'hidden' },
  fill: { height: '100%', borderRadius: 5 },
  pct: { fontSize: 13, fontWeight: '800', width: 38, textAlign: 'right' },
  count: { fontSize: 11, color: '#475569', width: 24, textAlign: 'right' },
});

function StrokeBar({ name, emoji, color, val, max }: { name: string; emoji: string; color: string; val: number; max: number }) {
  const pct = max > 0 ? (val / max) * 100 : 0;
  return (
    <View style={sb.row}>
      <Text style={sb.emoji}>{emoji}</Text>
      <Text style={sb.name} numberOfLines={1}>{name}</Text>
      <View style={sb.track}><View style={[sb.fill, { width: `${pct}%` as any, backgroundColor: color + 'cc' }]} /></View>
      <Text style={[sb.val, { color }]}>{val}</Text>
    </View>
  );
}
const sb = StyleSheet.create({
  row: { flexDirection: 'row', alignItems: 'center', gap: 8, paddingVertical: 3 },
  emoji: { fontSize: 14, width: 20, textAlign: 'center' },
  name: { fontSize: 11, color: '#94a3b8', width: 68 },
  track: { flex: 1, height: 8, backgroundColor: '#1e2d45', borderRadius: 4, overflow: 'hidden' },
  fill: { height: '100%', borderRadius: 4 },
  val: { fontSize: 13, fontWeight: '800', width: 28, textAlign: 'right' },
});

function EloSparkline({ profile, matches, color }: { profile: PlayerProfile; matches: MatchRecord[]; color: string }) {
  const profileMatches = matches
    .filter(m => m.profile1Id === profile.id || m.profile2Id === profile.id)
    .reverse();

  if (profileMatches.length === 0) {
    return (
      <View style={sp.empty}>
        <Text style={sp.emptyTxt}>Aucune donnée ELO pour {profile.name}</Text>
        <Text style={[sp.emptyTxt, { fontSize: 10, marginTop: 2 }]}>Lie ton profil avant de jouer pour suivre l'évolution</Text>
      </View>
    );
  }

  let elo = DEFAULT_ELO;
  const points: number[] = [elo];
  for (const m of profileMatches) {
    const delta = m.profile1Id === profile.id ? (m.eloChange1 ?? 0) : (m.eloChange2 ?? 0);
    elo += delta;
    points.push(elo);
  }

  const min = Math.min(...points);
  const max = Math.max(...points);
  const range = max - min || 1;
  const H = 48;

  return (
    <View style={sp.container}>
      <View style={sp.header}>
        <Text style={sp.name} numberOfLines={1}>{profile.name}</Text>
        <Text style={[sp.elo, { color }]}>{profile.elo} ELO</Text>
        <Text style={sp.delta}>{profile.elo - DEFAULT_ELO >= 0 ? '+' : ''}{profile.elo - DEFAULT_ELO}</Text>
      </View>
      <View style={[sp.chart, { height: H }]}>
        {points.map((p, i) => (
          <View key={i} style={[sp.bar, {
            height: Math.max(2, Math.round(((p - min) / range) * (H - 4))),
            backgroundColor: i === points.length - 1 ? color : color + '80',
            flex: 1,
          }]} />
        ))}
      </View>
      <View style={sp.labels}>
        <Text style={sp.label}>{min}</Text>
        <Text style={sp.label}>{max}</Text>
      </View>
    </View>
  );
}
const sp = StyleSheet.create({
  container: { gap: 8 },
  header: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  name: { flex: 1, fontSize: 13, fontWeight: '700', color: '#f1f5f9' },
  elo: { fontSize: 15, fontWeight: '900' },
  delta: { fontSize: 11, color: '#64748b' },
  chart: { flexDirection: 'row', alignItems: 'flex-end', gap: 2, backgroundColor: '#0a0f1e', borderRadius: 8, padding: 4 },
  bar: { borderRadius: 2 },
  labels: { flexDirection: 'row', justifyContent: 'space-between' },
  label: { fontSize: 10, color: '#475569' },
  empty: { paddingVertical: 8 },
  emptyTxt: { fontSize: 12, color: '#475569', fontStyle: 'italic' },
});

const PERIOD_LABELS: Record<Period, string> = {
  all: 'Tout', month: '30 jours', week: '7 jours', today: "Aujourd'hui",
};

const DAY_NAMES = ['Dim', 'Lun', 'Mar', 'Mer', 'Jeu', 'Ven', 'Sam'];

function HourChart({ matches }: { matches: MatchRecord[] }) {
  const counts = Array(24).fill(0);
  for (const m of matches) counts[new Date(m.date).getHours()]++;
  const maxCount = Math.max(...counts, 1);
  const peakHour = counts.indexOf(Math.max(...counts));
  // Only show hours with data + neighbors
  const hoursToShow = Array.from({ length: 24 }, (_, i) => i).filter(h => counts[h] > 0 || (h > 0 && counts[h-1] > 0) || (h < 23 && counts[h+1] > 0));
  if (hoursToShow.length === 0) return <Text style={{ color: '#475569', fontSize: 12 }}>Aucun match</Text>;

  return (
    <View style={{ gap: 6 }}>
      <View style={hc.row}>
        {Array.from({ length: 24 }, (_, h) => counts[h] > 0 ? h : null).filter(h => h !== null).map(h => (
          <View key={h} style={hc.barCol}>
            <View style={[hc.bar, { height: Math.max(4, (counts[h!] / maxCount) * 48), backgroundColor: h === peakHour ? ACCENT : ACCENT + '60' }]} />
            <Text style={hc.label}>{String(h).padStart(2,'0')}</Text>
          </View>
        ))}
      </View>
      <Text style={hc.hint}>Heure de pointe : {String(peakHour).padStart(2,'0')}h ({counts[peakHour]} matchs)</Text>
    </View>
  );
}
const hc = StyleSheet.create({
  row: { flexDirection: 'row', alignItems: 'flex-end', gap: 4, flexWrap: 'wrap' },
  barCol: { alignItems: 'center', gap: 2, minWidth: 20 },
  bar: { width: 18, borderRadius: 4 },
  label: { fontSize: 8, color: '#475569', fontWeight: '700' },
  hint: { fontSize: 11, color: '#64748b', fontStyle: 'italic' },
});

function DayChart({ matches }: { matches: MatchRecord[] }) {
  const counts = Array(7).fill(0);
  for (const m of matches) counts[new Date(m.date).getDay()]++;
  const maxCount = Math.max(...counts, 1);
  const peakDay = counts.indexOf(Math.max(...counts));

  return (
    <View style={{ gap: 6 }}>
      <View style={dc.row}>
        {DAY_NAMES.map((name, d) => (
          <View key={d} style={dc.barCol}>
            <Text style={[dc.count, { color: d === peakDay ? ACCENT : '#64748b' }]}>{counts[d]}</Text>
            <View style={[dc.bar, { height: Math.max(4, (counts[d] / maxCount) * 56), backgroundColor: d === peakDay ? ACCENT : ACCENT + '50' }]} />
            <Text style={[dc.label, d === peakDay && { color: ACCENT, fontWeight: '800' }]}>{name}</Text>
          </View>
        ))}
      </View>
      <Text style={dc.hint}>Jour favori : {DAY_NAMES[peakDay]} ({counts[peakDay]} matchs)</Text>
    </View>
  );
}
const dc = StyleSheet.create({
  row: { flexDirection: 'row', alignItems: 'flex-end', gap: 0 },
  barCol: { flex: 1, alignItems: 'center', gap: 2 },
  count: { fontSize: 10, fontWeight: '800' },
  bar: { width: '80%', borderRadius: 4 },
  label: { fontSize: 10, color: '#64748b', fontWeight: '600' },
  hint: { fontSize: 11, color: '#64748b', fontStyle: 'italic' },
});

export default function StatsScreen() {
  const nav = useNavigation<BottomTabNavigationProp<TabParams>>();
  const { loading, run } = useLoadingData();
  const [matches, setMatches] = useState<MatchRecord[]>([]);
  const [profiles, setProfiles] = useState<PlayerProfile[]>([]);
  const [h2pId1, setH2pId1] = useState<string | null>(null);
  const [h2pId2, setH2pId2] = useState<string | null>(null);
  const [period, setPeriod] = useState<Period>('all');
  const [tipProfileId, setTipProfileId] = useState<string | null>(null);
  const [shareProfile, setShareProfile] = useState<PlayerProfile | null>(null);

  useFocusEffect(useCallback(() => {
    run(() => Promise.all([loadMatches(), loadProfiles()]).then(([m, p]) => {
      setMatches(m);
      setProfiles([...p].sort((a, b) => b.elo - a.elo));
    }));
  }, [run]));

  // Period filter
  const now = new Date();
  const filteredMatches = period === 'all' ? matches : matches.filter(m => {
    const d = new Date(m.date);
    if (period === 'today') return d.toDateString() === now.toDateString();
    if (period === 'week') return d >= new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);
    return d >= new Date(now.getTime() - 30 * 24 * 60 * 60 * 1000);
  });

  const total = filteredMatches.length;
  const wins1 = filteredMatches.filter(m => m.winner === 0).length;
  const wins2 = filteredMatches.filter(m => m.winner === 1).length;
  const s1 = sumStrokes(filteredMatches, 'strokes1');
  const s2 = sumStrokes(filteredMatches, 'strokes2');
  const a1 = toArr(s1), a2 = toArr(s2);
  const max1 = Math.max(...a1, 1), max2 = Math.max(...a2, 1);
  const name1 = filteredMatches[0]?.player1 ?? matches[0]?.player1 ?? 'Joueur 1';
  const name2 = filteredMatches[0]?.player2 ?? matches[0]?.player2 ?? 'Joueur 2';
  const totalScore1 = filteredMatches.reduce((acc, m) => acc + m.score1, 0);
  const totalScore2 = filteredMatches.reduce((acc, m) => acc + m.score2, 0);
  const eloColors = [COLORS[0], COLORS[1], '#22c55e', '#f59e0b', '#c084fc'];

  const bestMatch = filteredMatches.length > 0 ? filteredMatches.reduce((a, b) =>
    Math.max(b.score1, b.score2) > Math.max(a.score1, a.score2) ? b : a
  ) : null;

  // H2H (use full match history for H2H, not filtered by period)
  const h2hMatches = h2pId1 && h2pId2 ? matches.filter(m =>
    (m.profile1Id === h2pId1 && m.profile2Id === h2pId2) ||
    (m.profile1Id === h2pId2 && m.profile2Id === h2pId1)
  ) : [];
  const h2prof1 = profiles.find(p => p.id === h2pId1);
  const h2prof2 = profiles.find(p => p.id === h2pId2);
  let h2w1 = 0, h2w2 = 0, h2s1 = 0, h2s2 = 0;
  let h2CurStreak1 = 0, h2CurStreak2 = 0;
  let h2Streak1 = 0, h2Streak2 = 0; // best streaks
  let h2BestScore1 = 0, h2BestScore2 = 0;
  let h2EloTotal1 = 0, h2EloTotal2 = 0;
  for (const m of h2hMatches) {
    const isP1 = m.profile1Id === h2pId1;
    if (isP1) {
      if (m.winner === 0) {
        h2w1++; h2CurStreak1++; h2CurStreak2 = 0;
        h2Streak1 = Math.max(h2Streak1, h2CurStreak1);
      } else {
        h2w2++; h2CurStreak2++; h2CurStreak1 = 0;
        h2Streak2 = Math.max(h2Streak2, h2CurStreak2);
      }
      h2s1 += m.score1; h2s2 += m.score2;
      h2BestScore1 = Math.max(h2BestScore1, m.score1);
      h2BestScore2 = Math.max(h2BestScore2, m.score2);
      h2EloTotal1 += (m.eloChange1 ?? 0);
      h2EloTotal2 += (m.eloChange2 ?? 0);
    } else {
      if (m.winner === 1) {
        h2w1++; h2CurStreak1++; h2CurStreak2 = 0;
        h2Streak1 = Math.max(h2Streak1, h2CurStreak1);
      } else {
        h2w2++; h2CurStreak2++; h2CurStreak1 = 0;
        h2Streak2 = Math.max(h2Streak2, h2CurStreak2);
      }
      h2s1 += m.score2; h2s2 += m.score1;
      h2BestScore1 = Math.max(h2BestScore1, m.score2);
      h2BestScore2 = Math.max(h2BestScore2, m.score1);
      h2EloTotal1 += (m.eloChange2 ?? 0);
      h2EloTotal2 += (m.eloChange1 ?? 0);
    }
  }
  const h2hLast5 = h2hMatches.slice(-5).reverse();

  // B3 – Forme du moment (ELO trend 7j vs 30j)
  const formeTrend = profiles.map(p => {
    const pm = matches.filter(m => m.profile1Id === p.id || m.profile2Id === p.id);
    const now2 = Date.now();
    const elo7 = pm.filter(m => new Date(m.date).getTime() >= now2 - 7 * 86400000)
      .reduce((acc, m) => acc + (m.profile1Id === p.id ? (m.eloChange1 ?? 0) : (m.eloChange2 ?? 0)), 0);
    const elo30 = pm.filter(m => new Date(m.date).getTime() >= now2 - 30 * 86400000)
      .reduce((acc, m) => acc + (m.profile1Id === p.id ? (m.eloChange1 ?? 0) : (m.eloChange2 ?? 0)), 0);
    return { id: p.id, name: p.name, elo7, elo30 };
  });

  // B2 – Situational stats
  const situProfile = profiles.find(p => p.id === tipProfileId) ?? profiles[0] ?? null;
  function computeSituational(profileId: string) {
    const pm = matches.filter(m => m.profile1Id === profileId || m.profile2Id === profileId);
    let equalWin = 0, equalTotal = 0, leadWin = 0, leadTotal = 0, comebackWin = 0, comebackTotal = 0;
    for (const m of pm) {
      const isP1 = m.profile1Id === profileId;
      if (!m.pointLog) continue;
      let maxLead = 0; let wasDown = false;
      for (const entry of m.pointLog) {
        const myScore = isP1 ? entry.score[0] : entry.score[1];
        const oppScore = isP1 ? entry.score[1] : entry.score[0];
        const diff = myScore - oppScore;
        if (diff >= 5) maxLead = Math.max(maxLead, diff);
        if (diff <= -5) wasDown = true;
        const isEqual = myScore === oppScore && myScore >= (m.config?.pointsToWin ?? 11) - 1;
        if (isEqual) {
          equalTotal++;
          const myWin = isP1 ? m.winner === 0 : m.winner === 1;
          if (myWin) equalWin++;
        }
      }
      if (maxLead >= 5) { leadTotal++; const myWin2 = isP1 ? m.winner === 0 : m.winner === 1; if (myWin2) leadWin++; }
      if (wasDown) { comebackTotal++; const myWin3 = isP1 ? m.winner === 0 : m.winner === 1; if (myWin3) comebackWin++; }
    }
    return { equalWin, equalTotal, leadWin, leadTotal, comebackWin, comebackTotal };
  }
  const situ = situProfile ? computeSituational(situProfile.id) : null;

  // AI Tips (always use full match history for profile-level analysis)
  const tipProfile = profiles.find(p => p.id === tipProfileId) ?? profiles[0] ?? null;
  const tips = generateTips(matches, tipProfile);
  const fatigued = tipProfile ? detectFatigue(matches, tipProfile.id) : false;

  if (loading) {
    return (
      <View style={[s.root, { flex: 1, alignItems: 'center', justifyContent: 'center' }]}>
        <ActivityIndicator color="#6366f1" size="large" />
      </View>
    );
  }

  return (
    <ScrollView style={s.root} contentContainerStyle={s.container} showsVerticalScrollIndicator={false}>
      <View style={{ flexDirection: 'row', alignItems: 'center', marginBottom: 4 }}>
        <Text style={[s.pageTitle, { flex: 1 }]}>Statistiques</Text>
        {profiles.length > 0 && (
          <TouchableOpacity
            style={{ padding: 8, backgroundColor: '#1e2d45', borderRadius: 10 }}
            onPress={() => setShareProfile(profiles[0])}
          >
            <Ionicons name="share-outline" size={18} color="#94a3b8" />
          </TouchableOpacity>
        )}
      </View>

      {/* Period filter */}
      <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ marginBottom: 2 }}>
        <View style={{ flexDirection: 'row', gap: 8 }}>
          {(['all', 'month', 'week', 'today'] as Period[]).map(p => (
            <TouchableOpacity
              key={p}
              style={[pf.chip, period === p && pf.chipActive]}
              onPress={() => setPeriod(p)}
            >
              <Text style={[pf.chipTxt, period === p && pf.chipTxtActive]}>{PERIOD_LABELS[p]}</Text>
            </TouchableOpacity>
          ))}
        </View>
      </ScrollView>

      {/* Share modal */}
      {shareProfile && (
        <Modal visible transparent animationType="fade">
          <StatShareCard profile={shareProfile} onClose={() => setShareProfile(null)} />
        </Modal>
      )}

      {total === 0 && profiles.length === 0 ? (
        <EmptyState
          icon="bar-chart-outline"
          title="Aucune statistique"
          subtitle="Joue tes premiers matchs et crée des profils joueurs pour voir tes stats ici"
          actionLabel="🏓 Jouer maintenant"
          onAction={() => nav.navigate('Play')}
        />
      ) : (
        <>
          {/* ── Face à Face ── */}
          {profiles.length >= 2 && (
            <View style={s.card}>
              <View style={s.cardHeader}>
                <Ionicons name="swap-horizontal-outline" size={16} color="#64748b" />
                <Text style={s.cardTitle}>Face à Face</Text>
              </View>
              <View style={{ gap: 8 }}>
                <View style={{ gap: 4 }}>
                  <Text style={h2h.lbl}>Joueur A</Text>
                  <ScrollView horizontal showsHorizontalScrollIndicator={false}>
                    <View style={{ flexDirection: 'row', gap: 6 }}>
                      {profiles.map(p => (
                        <TouchableOpacity
                          key={p.id}
                          style={[h2h.chip, p.id === h2pId1 && { borderColor: COLORS[0], backgroundColor: COLORS[0] + '20' }]}
                          onPress={() => setH2pId1(prev => prev === p.id ? null : p.id)}
                        >
                          <Text style={[h2h.chipTxt, p.id === h2pId1 && { color: COLORS[0] }]} numberOfLines={1}>{p.name}</Text>
                        </TouchableOpacity>
                      ))}
                    </View>
                  </ScrollView>
                </View>
                <View style={{ gap: 4 }}>
                  <Text style={h2h.lbl}>Joueur B</Text>
                  <ScrollView horizontal showsHorizontalScrollIndicator={false}>
                    <View style={{ flexDirection: 'row', gap: 6 }}>
                      {profiles.filter(p => p.id !== h2pId1).map(p => (
                        <TouchableOpacity
                          key={p.id}
                          style={[h2h.chip, p.id === h2pId2 && { borderColor: COLORS[1], backgroundColor: COLORS[1] + '20' }]}
                          onPress={() => setH2pId2(prev => prev === p.id ? null : p.id)}
                        >
                          <Text style={[h2h.chipTxt, p.id === h2pId2 && { color: COLORS[1] }]} numberOfLines={1}>{p.name}</Text>
                        </TouchableOpacity>
                      ))}
                    </View>
                  </ScrollView>
                </View>
              </View>
              {h2pId1 && h2pId2 ? (
                h2hMatches.length === 0 ? (
                  <Text style={h2h.noData}>Aucun match entre ces joueurs</Text>
                ) : (
                  <>
                    <View style={h2h.box}>
                      <View style={h2h.col}>
                        <Text style={[h2h.pName, { color: COLORS[0] }]} numberOfLines={1}>{h2prof1?.name}</Text>
                        <Text style={[h2h.wNum, { color: COLORS[0] }]}>{h2w1}</Text>
                        <Text style={h2h.wLbl}>victoires</Text>
                      </View>
                      <View style={h2h.mid}>
                        <Text style={h2h.midN}>{h2hMatches.length}</Text>
                        <Text style={h2h.midLbl}>matchs</Text>
                        <Text style={h2h.midScore}>{h2s1}–{h2s2}</Text>
                      </View>
                      <View style={h2h.col}>
                        <Text style={[h2h.pName, { color: COLORS[1] }]} numberOfLines={1}>{h2prof2?.name}</Text>
                        <Text style={[h2h.wNum, { color: COLORS[1] }]}>{h2w2}</Text>
                        <Text style={h2h.wLbl}>victoires</Text>
                      </View>
                    </View>
                    {/* B1 – Extended H2H stats */}
                    <View style={h2h.extraRow}>
                      <View style={h2h.extraCell}>
                        <Text style={h2h.extraLbl}>Série max</Text>
                        <Text style={[h2h.extraVal, { color: COLORS[0] }]}>{h2Streak1}</Text>
                      </View>
                      <View style={h2h.extraCell}>
                        <Text style={h2h.extraLbl}>Meilleur score</Text>
                        <Text style={h2h.extraVal}>{h2BestScore1}–{h2BestScore2}</Text>
                      </View>
                      <View style={h2h.extraCell}>
                        <Text style={h2h.extraLbl}>Série max</Text>
                        <Text style={[h2h.extraVal, { color: COLORS[1] }]}>{h2Streak2}</Text>
                      </View>
                    </View>
                    <View style={h2h.extraRow}>
                      <View style={{ flex: 1, alignItems: 'center' }}>
                        <Text style={h2h.extraLbl}>ELO échangé</Text>
                        <Text style={[h2h.extraVal, { color: h2EloTotal1 >= 0 ? '#4ade80' : '#f87171' }]}>
                          {h2prof1?.name?.slice(0,8)} {h2EloTotal1 >= 0 ? '+' : ''}{h2EloTotal1}
                        </Text>
                      </View>
                      <View style={{ flex: 1, alignItems: 'center' }}>
                        <Text style={h2h.extraLbl}>ELO échangé</Text>
                        <Text style={[h2h.extraVal, { color: h2EloTotal2 >= 0 ? '#4ade80' : '#f87171' }]}>
                          {h2prof2?.name?.slice(0,8)} {h2EloTotal2 >= 0 ? '+' : ''}{h2EloTotal2}
                        </Text>
                      </View>
                    </View>
                    {/* Last 5 H2H matches — compact chips */}
                    {h2hLast5.length > 0 && (
                      <View style={{ gap: 4 }}>
                        <Text style={h2h.lbl}>5 derniers</Text>
                        <View style={{ flexDirection: 'row', gap: 6, flexWrap: 'wrap' }}>
                          {h2hLast5.map(m => {
                            const isP1 = m.profile1Id === h2pId1;
                            const myWin = isP1 ? m.winner === 0 : m.winner === 1;
                            const sc1 = isP1 ? m.score1 : m.score2;
                            const sc2 = isP1 ? m.score2 : m.score1;
                            const col = myWin ? '#4ade80' : '#f87171';
                            return (
                              <View key={m.id} style={[h2h.h5chip, { borderColor: col + '60', backgroundColor: col + '15' }]}>
                                <Text style={[h2h.h5res, { color: col }]}>{myWin ? 'V' : 'D'}</Text>
                                <Text style={[h2h.h5score, { color: col }]}>{sc1}–{sc2}</Text>
                              </View>
                            );
                          })}
                        </View>
                      </View>
                    )}
                  </>
                )
              ) : (
                <Text style={h2h.hint}>Sélectionne 2 joueurs</Text>
              )}
            </View>
          )}

          {/* ── Séries ── */}
          {profiles.some(p => p.wins + p.losses > 0) && (
            <View style={s.card}>
              <View style={s.cardHeader}>
                <Ionicons name="flame-outline" size={16} color="#64748b" />
                <Text style={s.cardTitle}>Séries en cours</Text>
              </View>
              {profiles.filter(p => p.wins + p.losses > 0).slice(0, 5).map((p, i) => (
                <View key={p.id} style={streak.row}>
                  <Text style={streak.name} numberOfLines={1}>{p.name}</Text>
                  <Text style={streak.fire}>{p.currentStreak > 0 ? '🔥' : '❄️'}</Text>
                  <Text style={[streak.num, { color: eloColors[i % eloColors.length] }]}>{p.currentStreak}</Text>
                  <Text style={streak.sub}>en cours</Text>
                  <Text style={streak.best}>rec. {p.bestStreak}</Text>
                </View>
              ))}
            </View>
          )}

          {/* ── ELO Sparklines (full history) ── */}
          {profiles.length > 0 && (
            <View style={s.card}>
              <View style={s.cardHeader}>
                <Ionicons name="trending-up-outline" size={16} color="#64748b" />
                <Text style={s.cardTitle}>Évolution ELO</Text>
                <Text style={s.cardSub}>historique complet</Text>
              </View>
              {profiles.map((p, i) => (
                <View key={p.id} style={{ gap: 6 }}>
                  <EloSparkline profile={p} matches={matches} color={eloColors[i % eloColors.length]} />
                  <TouchableOpacity
                    style={{ flexDirection: 'row', alignItems: 'center', gap: 4, alignSelf: 'flex-end' }}
                    onPress={() => setShareProfile(p)}
                  >
                    <Ionicons name="share-outline" size={13} color="#475569" />
                    <Text style={{ fontSize: 11, color: '#475569' }}>Partager</Text>
                  </TouchableOpacity>
                </View>
              ))}
            </View>
          )}

          {total > 0 && (
            <>
              {/* ── Taux victoire ── */}
              <View style={s.card}>
                <View style={s.cardHeader}>
                  <Ionicons name="trophy-outline" size={16} color="#64748b" />
                  <Text style={s.cardTitle}>Taux de victoire</Text>
                  <Text style={s.cardSub}>{total} match{total > 1 ? 's' : ''}</Text>
                </View>
                <WinBar wins={wins1} total={total} color={COLORS[0]} name={name1} />
                <WinBar wins={wins2} total={total} color={COLORS[1]} name={name2} />
              </View>

              {/* ── Taux de conversion ── */}
              <View style={s.card}>
                <View style={s.cardHeader}>
                  <Ionicons name="checkmark-circle-outline" size={16} color="#64748b" />
                  <Text style={s.cardTitle}>Taux de conversion</Text>
                  <Text style={s.cardSub}>pts / frappes</Text>
                </View>
                <View style={conv.row}>
                  {[
                    { nm: name1, color: COLORS[0], strokes: s1, score: totalScore1 },
                    { nm: name2, color: COLORS[1], strokes: s2, score: totalScore2 },
                  ].map((p, i) => {
                    const tot = totalOf(p.strokes);
                    const rate = tot > 0 ? Math.round((p.score / tot) * 100) : 0;
                    return (
                      <View key={i} style={[conv.card, { borderColor: p.color + '40' }]}>
                        <Text style={[conv.name, { color: p.color }]} numberOfLines={1}>{p.nm}</Text>
                        <Text style={[conv.rate, { color: p.color }]}>{rate}%</Text>
                        <Text style={conv.sub}>{p.score} pts / {tot} frappes</Text>
                        <View style={conv.bar}>
                          <View style={[conv.fill, { width: `${Math.min(rate, 100)}%` as any, backgroundColor: p.color + 'cc' }]} />
                        </View>
                      </View>
                    );
                  })}
                </View>
              </View>

              {/* ── Coup favori ── */}
              <View style={s.card}>
                <View style={s.cardHeader}>
                  <Ionicons name="flash-outline" size={16} color="#64748b" />
                  <Text style={s.cardTitle}>Coup favori</Text>
                </View>
                <View style={s.favRow}>
                  {[{ name: name1, fav: favoriteStroke(s1), color: COLORS[0] },
                    { name: name2, fav: favoriteStroke(s2), color: COLORS[1] }].map((p, i) => {
                    const si = ['BH Drive', 'BH Smash', 'FH Drive', 'FH Loop', 'FH Smash'].indexOf(p.fav);
                    return (
                      <View key={i} style={[s.favCard, { borderColor: p.color + '40', backgroundColor: p.color + '08' }]}>
                        <Text style={[s.favPlayerName, { color: p.color }]} numberOfLines={1}>{p.name}</Text>
                        <Text style={s.favEmoji}>{si >= 0 ? STROKES[si].emoji : '–'}</Text>
                        <Text style={s.favStroke}>{p.fav}</Text>
                      </View>
                    );
                  })}
                </View>
              </View>

              {/* ── Coups J1 ── */}
              <View style={s.card}>
                <View style={s.cardHeader}>
                  <View style={[s.dot, { backgroundColor: COLORS[0] }]} />
                  <Text style={s.cardTitle}>{name1}</Text>
                </View>
                {STROKES.map((st, i) => (
                  <StrokeBar key={i} name={st.name} emoji={st.emoji} color={COLORS[0]} val={a1[i]} max={max1} />
                ))}
              </View>

              {/* ── Coups J2 ── */}
              <View style={s.card}>
                <View style={s.cardHeader}>
                  <View style={[s.dot, { backgroundColor: COLORS[1] }]} />
                  <Text style={s.cardTitle}>{name2}</Text>
                </View>
                {STROKES.map((st, i) => (
                  <StrokeBar key={i} name={st.name} emoji={st.emoji} color={COLORS[1]} val={a2[i]} max={max2} />
                ))}
              </View>

              {/* ── Meilleur score ── */}
              {bestMatch && (
                <View style={[s.card, { alignItems: 'center', gap: 6 }]}>
                  <View style={s.cardHeader}>
                    <Ionicons name="medal-outline" size={16} color="#f59e0b" />
                    <Text style={s.cardTitle}>Meilleur score</Text>
                  </View>
                  <Text style={s.bestScore}>{bestMatch.score1} – {bestMatch.score2}</Text>
                  <Text style={s.bestNames}>{bestMatch.player1} vs {bestMatch.player2}</Text>
                </View>
              )}
            </>
          )}

          {/* ── Performance par heure ── */}
          {total > 0 && (
            <View style={s.card}>
              <View style={s.cardHeader}>
                <Ionicons name="time-outline" size={16} color="#64748b" />
                <Text style={s.cardTitle}>Performance par heure</Text>
                <Text style={s.cardSub}>matchs joués</Text>
              </View>
              <HourChart matches={filteredMatches} />
            </View>
          )}

          {/* ── Performance par jour de semaine ── */}
          {total > 0 && (
            <View style={s.card}>
              <View style={s.cardHeader}>
                <Ionicons name="calendar-outline" size={16} color="#64748b" />
                <Text style={s.cardTitle}>Activité par jour</Text>
                <Text style={s.cardSub}>matchs / jour</Text>
              </View>
              <DayChart matches={filteredMatches} />
            </View>
          )}

          {/* ── B3 Forme du moment ── */}
          {profiles.length > 0 && formeTrend.some(f => f.elo30 !== 0) && (
            <View style={s.card}>
              <View style={s.cardHeader}>
                <Ionicons name="trending-up-outline" size={16} color="#64748b" />
                <Text style={s.cardTitle}>Forme du moment</Text>
                <Text style={s.cardSub}>7j / 30j</Text>
              </View>
              {formeTrend.filter(f => f.elo30 !== 0).map((f, i) => {
                const arrow = f.elo30 > 20 ? '↑' : f.elo30 < -20 ? '↓' : '→';
                const color = f.elo30 > 20 ? '#4ade80' : f.elo30 < -20 ? '#f87171' : '#94a3b8';
                return (
                  <View key={f.id} style={forme.row}>
                    <Text style={forme.name} numberOfLines={1}>{f.name}</Text>
                    <Text style={[forme.arrow, { color }]}>{arrow}</Text>
                    <Text style={[forme.delta, { color }]}>
                      {f.elo30 >= 0 ? '+' : ''}{f.elo30} ELO ce mois
                    </Text>
                    <Text style={forme.sub7}>{f.elo7 >= 0 ? '+' : ''}{f.elo7} / 7j</Text>
                  </View>
                );
              })}
            </View>
          )}

          {/* ── B2 Situations clés ── */}
          {situ && (situ.equalTotal > 0 || situ.leadTotal > 0 || situ.comebackTotal > 0) && (
            <View style={s.card}>
              <View style={s.cardHeader}>
                <Ionicons name="git-branch-outline" size={16} color="#64748b" />
                <Text style={s.cardTitle}>Situations clés</Text>
                <Text style={s.cardSub}>{situProfile?.name}</Text>
              </View>
              <View style={situ2.row}>
                {situ.equalTotal > 0 && (
                  <View style={situ2.cell}>
                    <Text style={situ2.emoji}>⚖️</Text>
                    <Text style={situ2.pct}>{Math.round((situ.equalWin / situ.equalTotal) * 100)}%</Text>
                    <Text style={situ2.lbl}>Égalité</Text>
                    <Text style={situ2.sub}>{situ.equalWin}/{situ.equalTotal}</Text>
                  </View>
                )}
                {situ.leadTotal > 0 && (
                  <View style={situ2.cell}>
                    <Text style={situ2.emoji}>🚀</Text>
                    <Text style={situ2.pct}>{Math.round((situ.leadWin / situ.leadTotal) * 100)}%</Text>
                    <Text style={situ2.lbl}>En tête +5</Text>
                    <Text style={situ2.sub}>{situ.leadWin}/{situ.leadTotal}</Text>
                  </View>
                )}
                {situ.comebackTotal > 0 && (
                  <View style={situ2.cell}>
                    <Text style={situ2.emoji}>🔄</Text>
                    <Text style={situ2.pct}>{Math.round((situ.comebackWin / situ.comebackTotal) * 100)}%</Text>
                    <Text style={situ2.lbl}>Retard -5</Text>
                    <Text style={situ2.sub}>{situ.comebackWin}/{situ.comebackTotal}</Text>
                  </View>
                )}
              </View>
            </View>
          )}

          {/* ── Conseils IA ── */}
          {profiles.length > 0 && (
            <View style={s.card}>
              <View style={s.cardHeader}>
                <Ionicons name="bulb-outline" size={16} color="#f59e0b" />
                <Text style={s.cardTitle}>Conseils IA</Text>
                <Text style={s.cardSub}>personnalisés</Text>
              </View>

              {/* Profile selector */}
              {profiles.length > 1 && (
                <ScrollView horizontal showsHorizontalScrollIndicator={false}>
                  <View style={{ flexDirection: 'row', gap: 6 }}>
                    {profiles.map(p => (
                      <TouchableOpacity
                        key={p.id}
                        style={[tip.chip, tipProfileId === p.id && tip.chipActive]}
                        onPress={() => setTipProfileId(prev => prev === p.id ? null : p.id)}
                      >
                        <Text style={[tip.chipTxt, tipProfileId === p.id && tip.chipTxtActive]} numberOfLines={1}>{p.name}</Text>
                      </TouchableOpacity>
                    ))}
                  </View>
                </ScrollView>
              )}

              {/* Fatigue warning */}
              {fatigued && (
                <View style={tip.fatigueBanner}>
                  <Ionicons name="warning-outline" size={14} color="#f59e0b" />
                  <Text style={tip.fatigueTxt}>Fatigue détectée — performances en baisse sur tes derniers matchs</Text>
                </View>
              )}

              {/* Tips list */}
              {tips.length === 0 && (
                <Text style={{ fontSize: 12, color: '#475569', fontStyle: 'italic' }}>
                  Joue plus de matchs pour obtenir des conseils personnalisés.
                </Text>
              )}
              {tips.map((t, i) => (
                <View key={t.id} style={[tip.row, i === 0 && tip.rowFirst]}>
                  <Text style={tip.emoji}>{t.emoji}</Text>
                  <View style={{ flex: 1, gap: 2 }}>
                    <Text style={tip.title}>{t.title}</Text>
                    <Text style={tip.body}>{t.body}</Text>
                  </View>
                  {i === 0 && <View style={tip.priorityDot} />}
                </View>
              ))}
              {/* Share tip profile */}
              {tipProfile && (
                <TouchableOpacity
                  style={{ flexDirection: 'row', alignItems: 'center', gap: 4, alignSelf: 'flex-end', paddingTop: 4 }}
                  onPress={() => setShareProfile(tipProfile)}
                >
                  <Ionicons name="share-outline" size={12} color="#475569" />
                  <Text style={{ fontSize: 11, color: '#475569' }}>Partager les stats</Text>
                </TouchableOpacity>
              )}
            </View>
          )}
        </>
      )}
    </ScrollView>
  );
}

const s = StyleSheet.create({
  root: { flex: 1, backgroundColor: BG },
  container: { padding: 16, gap: 14, paddingBottom: 32 },
  pageTitle: { fontSize: 26, fontWeight: '900', color: '#f1f5f9', marginBottom: 4 },
  card: { backgroundColor: CARD_BG, borderRadius: 20, padding: 16, gap: 12, borderWidth: 1, borderColor: '#1e2d45' },
  cardHeader: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  cardTitle: { flex: 1, fontSize: 12, fontWeight: '700', color: '#64748b', textTransform: 'uppercase', letterSpacing: 0.8 },
  cardSub: { fontSize: 11, color: '#334155' },
  dot: { width: 8, height: 8, borderRadius: 4 },
  favRow: { flexDirection: 'row', gap: 10 },
  favCard: { flex: 1, alignItems: 'center', gap: 4, borderWidth: 1, borderRadius: 14, paddingVertical: 14, paddingHorizontal: 8 },
  favPlayerName: { fontSize: 12, fontWeight: '700' },
  favEmoji: { fontSize: 26 },
  favStroke: { fontSize: 11, color: '#94a3b8', fontWeight: '600' },
  bestScore: { fontSize: 40, fontWeight: '900', color: '#f1f5f9' },
  bestNames: { fontSize: 12, color: '#475569' },
  empty: { flex: 1, alignItems: 'center', justifyContent: 'center', gap: 12, padding: 40, marginTop: 60 },
  emptyIcon: { width: 80, height: 80, borderRadius: 40, backgroundColor: '#6366f115', alignItems: 'center', justifyContent: 'center' },
  emptyTxt: { fontSize: 17, color: '#f1f5f9', fontWeight: '700' },
  emptyHint: { fontSize: 13, color: '#64748b', textAlign: 'center' },
});

const pf = StyleSheet.create({
  chip: { paddingHorizontal: 14, paddingVertical: 7, borderRadius: 20, borderWidth: 1.5, borderColor: '#1e2d45', backgroundColor: '#0a0f1e' },
  chipActive: { borderColor: ACCENT, backgroundColor: ACCENT + '20' },
  chipTxt: { fontSize: 12, color: '#475569', fontWeight: '700' },
  chipTxtActive: { color: ACCENT },
});

const h2h = StyleSheet.create({
  lbl: { fontSize: 11, color: '#64748b', fontWeight: '700', textTransform: 'uppercase', letterSpacing: 0.5 },
  chip: { paddingHorizontal: 12, paddingVertical: 7, borderRadius: 10, borderWidth: 1.5, borderColor: '#1e2d45', backgroundColor: '#0a0f1e' },
  chipTxt: { fontSize: 12, color: '#64748b', fontWeight: '700' },
  hint: { fontSize: 12, color: '#334155', textAlign: 'center', fontStyle: 'italic' },
  noData: { fontSize: 12, color: '#475569', textAlign: 'center', fontStyle: 'italic', paddingVertical: 4 },
  box: { flexDirection: 'row', alignItems: 'center', backgroundColor: '#0a0f1e', borderRadius: 14, padding: 12 },
  col: { flex: 1, alignItems: 'center', gap: 4 },
  pName: { fontSize: 13, fontWeight: '800' },
  wNum: { fontSize: 32, fontWeight: '900', lineHeight: 38 },
  wLbl: { fontSize: 10, color: '#64748b', fontWeight: '600' },
  mid: { alignItems: 'center', gap: 2, paddingHorizontal: 12 },
  midN: { fontSize: 20, fontWeight: '900', color: '#f1f5f9' },
  midLbl: { fontSize: 10, color: '#475569', fontWeight: '600' },
  midScore: { fontSize: 12, color: '#64748b', fontWeight: '700' },
  // B1 – extended
  extraRow: { flexDirection: 'row', gap: 6 },
  extraCell: { flex: 1, alignItems: 'center', backgroundColor: '#0a0f1e', borderRadius: 10, paddingVertical: 6 },
  extraLbl: { fontSize: 9, color: '#475569', fontWeight: '700', textTransform: 'uppercase', letterSpacing: 0.4 },
  extraVal: { fontSize: 15, fontWeight: '900', color: '#f1f5f9' },
  h5row: { flexDirection: 'row', alignItems: 'center', gap: 8, paddingVertical: 4, borderTopWidth: 1, borderTopColor: '#1e2d4530' },
  h5chip: { flexDirection: 'row', alignItems: 'center', gap: 4, paddingHorizontal: 8, paddingVertical: 4, borderRadius: 8, borderWidth: 1 },
  h5res: { fontSize: 13, fontWeight: '900', width: 16, textAlign: 'center' },
  h5score: { flex: 1, fontSize: 12, color: '#f1f5f9', fontWeight: '700' },
  h5date: { fontSize: 11, color: '#475569' },
});

const streak = StyleSheet.create({
  row: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  name: { flex: 1, fontSize: 13, fontWeight: '700', color: '#f1f5f9' },
  fire: { fontSize: 16 },
  num: { fontSize: 20, fontWeight: '900', minWidth: 28, textAlign: 'center' },
  sub: { fontSize: 10, color: '#475569', width: 50 },
  best: { fontSize: 11, color: '#334155', fontWeight: '600' },
});

const conv = StyleSheet.create({
  row: { flexDirection: 'row', gap: 10 },
  card: { flex: 1, borderWidth: 1, borderRadius: 14, padding: 12, gap: 6, alignItems: 'center', backgroundColor: '#0a0f1e' },
  name: { fontSize: 12, fontWeight: '700' },
  rate: { fontSize: 28, fontWeight: '900' },
  sub: { fontSize: 10, color: '#475569', textAlign: 'center' },
  bar: { width: '100%', height: 6, backgroundColor: '#1e2d45', borderRadius: 3, overflow: 'hidden' },
  fill: { height: '100%', borderRadius: 3 },
});

const forme = StyleSheet.create({
  row: { flexDirection: 'row', alignItems: 'center', gap: 8, paddingVertical: 4 },
  name: { flex: 1, fontSize: 13, fontWeight: '700', color: '#f1f5f9' },
  arrow: { fontSize: 22, fontWeight: '900', lineHeight: 26 },
  delta: { fontSize: 12, fontWeight: '800' },
  sub7: { fontSize: 11, color: '#475569', fontWeight: '600' },
});

const situ2 = StyleSheet.create({
  row: { flexDirection: 'row', gap: 8, flexWrap: 'wrap' },
  cell: { flex: 1, minWidth: 80, alignItems: 'center', backgroundColor: '#0a0f1e', borderRadius: 12, padding: 10, gap: 2 },
  emoji: { fontSize: 20 },
  pct: { fontSize: 22, fontWeight: '900', color: '#f1f5f9' },
  lbl: { fontSize: 10, color: '#64748b', fontWeight: '700', textAlign: 'center' },
  sub: { fontSize: 10, color: '#334155' },
});

const tip = StyleSheet.create({
  chip: { paddingHorizontal: 12, paddingVertical: 6, borderRadius: 10, borderWidth: 1.5, borderColor: '#1e2d45', backgroundColor: '#0a0f1e' },
  chipActive: { borderColor: '#f59e0b', backgroundColor: '#f59e0b20' },
  chipTxt: { fontSize: 12, color: '#64748b', fontWeight: '700' },
  chipTxtActive: { color: '#f59e0b' },
  fatigueBanner: { flexDirection: 'row', alignItems: 'center', gap: 8, backgroundColor: '#f59e0b15', borderWidth: 1, borderColor: '#f59e0b40', borderRadius: 10, padding: 10 },
  fatigueTxt: { flex: 1, fontSize: 12, color: '#f59e0b', fontWeight: '600' },
  row: { flexDirection: 'row', gap: 12, paddingVertical: 6, borderTopWidth: 1, borderTopColor: '#1e2d4530', alignItems: 'flex-start' },
  rowFirst: { backgroundColor: '#f59e0b08', borderRadius: 10, paddingHorizontal: 8, borderTopWidth: 0, marginTop: 4 },
  emoji: { fontSize: 22, width: 30, textAlign: 'center', marginTop: 2 },
  title: { fontSize: 13, fontWeight: '800', color: '#f1f5f9' },
  body: { fontSize: 12, color: '#64748b', lineHeight: 17, marginTop: 1 },
  priorityDot: { width: 6, height: 6, borderRadius: 3, backgroundColor: '#f59e0b', marginTop: 6 },
});
