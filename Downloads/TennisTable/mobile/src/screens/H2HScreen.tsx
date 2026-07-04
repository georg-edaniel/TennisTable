import React, { useCallback, useState } from 'react';
import { ScrollView, StyleSheet, Text, TouchableOpacity, View } from 'react-native';
import { useFocusEffect } from '@react-navigation/native';
import { Ionicons } from '@expo/vector-icons';
import { loadMatches } from '../storage/matchStorage';
import { loadProfiles } from '../storage/profileStorage';
import { BG, CARD_BG, MatchRecord, PlayerProfile } from '../types';
import { getLevel } from '../services/levelService';

const ACCENT = '#6366f1';
const C1 = '#6366f1';
const C2 = '#f43f5e';

function pct(n: number, total: number) {
  return total > 0 ? Math.round((n / total) * 100) : 0;
}

function fmtDate(iso: string) {
  return new Date(iso).toLocaleDateString('fr-FR', { day: '2-digit', month: 'short' });
}

function WinBar({ wins, total, color, name }: { wins: number; total: number; color: string; name: string }) {
  const p = total > 0 ? (wins / total) * 100 : 0;
  return (
    <View style={wb.row}>
      <Text style={[wb.name, { color }]} numberOfLines={1}>{name}</Text>
      <View style={wb.track}>
        <View style={[wb.fill, { width: `${p}%` as any, backgroundColor: color }]} />
      </View>
      <Text style={[wb.pct, { color }]}>{Math.round(p)}%</Text>
    </View>
  );
}
const wb = StyleSheet.create({
  row: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  name: { width: 80, fontSize: 13, fontWeight: '700' },
  track: { flex: 1, height: 10, backgroundColor: '#1e2d45', borderRadius: 5, overflow: 'hidden' },
  fill: { height: '100%', borderRadius: 5 },
  pct: { fontSize: 13, fontWeight: '800', width: 36, textAlign: 'right' },
});

export default function H2HScreen() {
  const [profiles, setProfiles] = useState<PlayerProfile[]>([]);
  const [matches, setMatches] = useState<MatchRecord[]>([]);
  const [p1Id, setP1Id] = useState<string | null>(null);
  const [p2Id, setP2Id] = useState<string | null>(null);
  const [step, setStep] = useState<'pick1' | 'pick2' | 'result'>('pick1');

  useFocusEffect(useCallback(() => {
    Promise.all([loadProfiles(), loadMatches()]).then(([profs, ms]) => {
      setProfiles(profs);
      setMatches(ms);
    });
    return () => {
      setP1Id(null); setP2Id(null); setStep('pick1');
    };
  }, []));

  const p1 = profiles.find(p => p.id === p1Id) ?? null;
  const p2 = profiles.find(p => p.id === p2Id) ?? null;

  // H2H matches between p1 and p2
  const h2hMatches = matches.filter(m => {
    const inv1 = m.profile1Id === p1Id && m.profile2Id === p2Id;
    const inv2 = m.profile1Id === p2Id && m.profile2Id === p1Id;
    return inv1 || inv2;
  }).sort((a, b) => new Date(b.date).getTime() - new Date(a.date).getTime());

  const p1Wins = h2hMatches.filter(m => {
    const isP1inSlot1 = m.profile1Id === p1Id;
    return isP1inSlot1 ? m.winner === 0 : m.winner === 1;
  }).length;
  const p2Wins = h2hMatches.length - p1Wins;

  function pickProfile(id: string) {
    if (step === 'pick1') {
      setP1Id(id);
      setStep('pick2');
    } else if (step === 'pick2') {
      if (id === p1Id) return; // same player
      setP2Id(id);
      setStep('result');
    }
  }

  function reset() {
    setP1Id(null); setP2Id(null); setStep('pick1');
  }

  if (step !== 'result') {
    return (
      <View style={s.root}>
        <View style={s.header}>
          <Text style={s.title}>⚔️ Face à Face</Text>
          <Text style={s.subtitle}>
            {step === 'pick1' ? 'Sélectionne le joueur 1' : `vs ${p1?.name ?? '?'} — Sélectionne le joueur 2`}
          </Text>
        </View>
        {step === 'pick2' && (
          <View style={s.selectedBanner}>
            <View style={[s.elo, { backgroundColor: C1 + '20' }]}>
              <Text style={[s.eloTxt, { color: C1 }]}>{p1?.elo ?? '?'} ELO</Text>
            </View>
            <Text style={s.selectedName}>{p1?.name}</Text>
          </View>
        )}
        <ScrollView showsVerticalScrollIndicator={false}>
          <View style={s.profileList}>
            {profiles.map(p => {
              const level = getLevel(p.elo);
              const disabled = step === 'pick2' && p.id === p1Id;
              return (
                <TouchableOpacity
                  key={p.id}
                  style={[s.profileCard, disabled && { opacity: 0.35 }]}
                  onPress={() => pickProfile(p.id)}
                  disabled={disabled}
                  accessibilityLabel={`Sélectionner ${p.name}`}
                >
                  <View style={[s.avatar, { backgroundColor: level.color + '25' }]}>
                    <Text style={s.avatarEmoji}>{level.emoji}</Text>
                  </View>
                  <View style={{ flex: 1 }}>
                    <Text style={s.profileName}>{p.name}</Text>
                    <Text style={[s.profileLevel, { color: level.color }]}>{level.name}</Text>
                  </View>
                  <View style={s.eloBox}>
                    <Text style={[s.eloNum, { color: level.color }]}>{p.elo}</Text>
                    <Text style={s.eloLabel}>ELO</Text>
                  </View>
                  <Text style={s.wr}>{pct(p.wins, p.wins + p.losses)}%</Text>
                </TouchableOpacity>
              );
            })}
          </View>
        </ScrollView>
      </View>
    );
  }

  if (!p1 || !p2) return null;

  const level1 = getLevel(p1.elo);
  const level2 = getLevel(p2.elo);
  const eloDiff = p1.elo - p2.elo;

  return (
    <ScrollView style={s.root} contentContainerStyle={s.content} showsVerticalScrollIndicator={false}>
      {/* Header */}
      <View style={s.header}>
        <Text style={s.title}>⚔️ Face à Face</Text>
        <TouchableOpacity onPress={reset} style={s.resetBtn} accessibilityLabel="Changer les joueurs">
          <Ionicons name="refresh-outline" size={14} color="#94a3b8" />
          <Text style={s.resetTxt}>Changer</Text>
        </TouchableOpacity>
      </View>

      {/* Players card */}
      <View style={s.vsCard}>
        <View style={s.playerCol}>
          <View style={[s.avatar, { backgroundColor: level1.color + '25' }]}>
            <Text style={s.avatarEmoji}>{level1.emoji}</Text>
          </View>
          <Text style={s.vsName} numberOfLines={1}>{p1.name}</Text>
          <Text style={[s.vsLevel, { color: level1.color }]}>{level1.name}</Text>
          <Text style={[s.vsElo, { color: level1.color }]}>{p1.elo}</Text>
        </View>
        <View style={s.vsCenter}>
          <Text style={s.vsText}>VS</Text>
          {eloDiff !== 0 && (
            <Text style={[s.eloDiffTxt, { color: eloDiff > 0 ? C1 : C2 }]}>
              {eloDiff > 0 ? `+${eloDiff}` : eloDiff}
            </Text>
          )}
        </View>
        <View style={s.playerCol}>
          <View style={[s.avatar, { backgroundColor: level2.color + '25' }]}>
            <Text style={s.avatarEmoji}>{level2.emoji}</Text>
          </View>
          <Text style={s.vsName} numberOfLines={1}>{p2.name}</Text>
          <Text style={[s.vsLevel, { color: level2.color }]}>{level2.name}</Text>
          <Text style={[s.vsElo, { color: level2.color }]}>{p2.elo}</Text>
        </View>
      </View>

      {/* H2H record */}
      <View style={s.card}>
        <Text style={s.cardTitle}>BILAN FACE À FACE</Text>
        {h2hMatches.length === 0 ? (
          <View style={{ alignItems: 'center', paddingVertical: 16 }}>
            <Text style={{ fontSize: 28, marginBottom: 6 }}>🤝</Text>
            <Text style={{ color: '#64748b', fontSize: 13 }}>Aucun match direct enregistré</Text>
          </View>
        ) : (
          <>
            <View style={s.scoreRow}>
              <Text style={[s.bigScore, { color: p1Wins >= p2Wins ? C1 : '#475569' }]}>{p1Wins}</Text>
              <Text style={s.scoreDash}>–</Text>
              <Text style={[s.bigScore, { color: p2Wins > p1Wins ? C2 : '#475569' }]}>{p2Wins}</Text>
            </View>
            <View style={{ gap: 6 }}>
              <WinBar wins={p1Wins} total={h2hMatches.length} color={C1} name={p1.name} />
              <WinBar wins={p2Wins} total={h2hMatches.length} color={C2} name={p2.name} />
            </View>
          </>
        )}
      </View>

      {/* Global stats comparison */}
      <View style={s.card}>
        <Text style={s.cardTitle}>STATS GLOBALES</Text>
        <View style={s.statsGrid}>
          {[
            { label: 'Win Rate', v1: `${pct(p1.wins, p1.wins + p1.losses)}%`, v2: `${pct(p2.wins, p2.wins + p2.losses)}%`, c1: pct(p1.wins, p1.wins + p1.losses) >= pct(p2.wins, p2.wins + p2.losses) ? C1 : '#475569', c2: pct(p2.wins, p2.wins + p2.losses) > pct(p1.wins, p1.wins + p1.losses) ? C2 : '#475569' },
            { label: 'Victoires', v1: String(p1.wins), v2: String(p2.wins), c1: p1.wins >= p2.wins ? C1 : '#475569', c2: p2.wins > p1.wins ? C2 : '#475569' },
            { label: 'ELO', v1: String(p1.elo), v2: String(p2.elo), c1: p1.elo >= p2.elo ? C1 : '#475569', c2: p2.elo > p1.elo ? C2 : '#475569' },
            { label: 'Séries', v1: String(p1.currentStreak), v2: String(p2.currentStreak), c1: p1.currentStreak >= p2.currentStreak ? C1 : '#475569', c2: p2.currentStreak > p1.currentStreak ? C2 : '#475569' },
          ].map(row => (
            <View key={row.label} style={s.statRow}>
              <Text style={[s.statVal, { color: row.c1 }]}>{row.v1}</Text>
              <Text style={s.statLabel}>{row.label}</Text>
              <Text style={[s.statVal, { color: row.c2, textAlign: 'right' }]}>{row.v2}</Text>
            </View>
          ))}
        </View>
      </View>

      {/* Recent H2H results */}
      {h2hMatches.length > 0 && (
        <View style={s.card}>
          <Text style={s.cardTitle}>DERNIERS RÉSULTATS</Text>
          <View style={{ gap: 8 }}>
            {h2hMatches.slice(0, 6).map(m => {
              const isP1inSlot1 = m.profile1Id === p1Id;
              const p1Score = isP1inSlot1 ? m.score1 : m.score2;
              const p2Score = isP1inSlot1 ? m.score2 : m.score1;
              const p1Won = isP1inSlot1 ? m.winner === 0 : m.winner === 1;
              return (
                <View key={m.id} style={s.matchRow}>
                  <Text style={s.matchDate}>{fmtDate(m.date)}</Text>
                  <View style={s.matchScoreRow}>
                    <Text style={[s.matchScore, { color: p1Won ? C1 : '#475569' }]}>{p1Score}</Text>
                    <Text style={s.matchDash}>–</Text>
                    <Text style={[s.matchScore, { color: !p1Won ? C2 : '#475569' }]}>{p2Score}</Text>
                  </View>
                  <View style={[s.matchWinBadge, { backgroundColor: p1Won ? C1 + '25' : C2 + '25' }]}>
                    <Text style={[s.matchWinTxt, { color: p1Won ? C1 : C2 }]}>
                      {p1Won ? p1.name : p2.name}
                    </Text>
                  </View>
                </View>
              );
            })}
          </View>
        </View>
      )}

      <View style={{ height: 40 }} />
    </ScrollView>
  );
}

const s = StyleSheet.create({
  root: { flex: 1, backgroundColor: BG },
  content: { padding: 20, paddingTop: 50, gap: 16 },
  header: { flexDirection: 'row', alignItems: 'flex-start', justifyContent: 'space-between', paddingTop: 50, paddingHorizontal: 20, paddingBottom: 16 },
  title: { fontSize: 26, fontWeight: '900', color: '#f1f5f9' },
  subtitle: { fontSize: 13, color: '#475569', marginTop: 4, paddingHorizontal: 20, paddingBottom: 8 },
  resetBtn: { flexDirection: 'row', alignItems: 'center', gap: 4, paddingHorizontal: 10, paddingVertical: 6, backgroundColor: '#1e2d45', borderRadius: 8, marginTop: 4 },
  resetTxt: { color: '#94a3b8', fontSize: 12, fontWeight: '700' },

  selectedBanner: { flexDirection: 'row', alignItems: 'center', gap: 10, marginHorizontal: 20, marginBottom: 12, backgroundColor: C1 + '15', borderRadius: 12, padding: 12, borderWidth: 1, borderColor: C1 + '30' },
  elo: { paddingHorizontal: 8, paddingVertical: 3, borderRadius: 8 },
  eloTxt: { fontSize: 12, fontWeight: '800' },
  selectedName: { fontSize: 15, fontWeight: '800', color: '#f1f5f9', flex: 1 },

  profileList: { gap: 10, paddingHorizontal: 20, paddingBottom: 40 },
  profileCard: { flexDirection: 'row', alignItems: 'center', gap: 12, backgroundColor: CARD_BG, borderRadius: 16, padding: 14, borderWidth: 1, borderColor: '#1e2d45' },
  avatar: { width: 46, height: 46, borderRadius: 23, alignItems: 'center', justifyContent: 'center' },
  avatarEmoji: { fontSize: 22 },
  profileName: { fontSize: 15, fontWeight: '800', color: '#f1f5f9' },
  profileLevel: { fontSize: 11, fontWeight: '700' },
  eloBox: { alignItems: 'flex-end' },
  eloNum: { fontSize: 18, fontWeight: '900' },
  eloLabel: { fontSize: 9, color: '#475569', fontWeight: '700', letterSpacing: 1 },
  wr: { fontSize: 12, color: '#64748b', fontWeight: '700', width: 36, textAlign: 'right' },

  vsCard: { flexDirection: 'row', alignItems: 'center', backgroundColor: CARD_BG, borderRadius: 20, padding: 20, borderWidth: 1, borderColor: '#1e2d45' },
  playerCol: { flex: 1, alignItems: 'center', gap: 6 },
  vsName: { fontSize: 15, fontWeight: '900', color: '#f1f5f9', textAlign: 'center' },
  vsLevel: { fontSize: 11, fontWeight: '700' },
  vsElo: { fontSize: 22, fontWeight: '900' },
  vsCenter: { alignItems: 'center', paddingHorizontal: 12 },
  vsText: { fontSize: 18, fontWeight: '900', color: '#1e2d45' },
  eloDiffTxt: { fontSize: 12, fontWeight: '700' },

  card: { backgroundColor: CARD_BG, borderRadius: 18, padding: 16, gap: 14, borderWidth: 1, borderColor: '#1e2d45' },
  cardTitle: { fontSize: 11, fontWeight: '700', color: '#475569', letterSpacing: 1 },

  scoreRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 20 },
  bigScore: { fontSize: 56, fontWeight: '900', lineHeight: 64 },
  scoreDash: { fontSize: 28, color: '#1e2d45' },

  statsGrid: { gap: 10 },
  statRow: { flexDirection: 'row', alignItems: 'center' },
  statVal: { flex: 1, fontSize: 16, fontWeight: '900' },
  statLabel: { fontSize: 11, color: '#64748b', fontWeight: '700', textAlign: 'center', width: 80, letterSpacing: 0.5 },

  matchRow: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  matchDate: { fontSize: 11, color: '#475569', width: 52 },
  matchScoreRow: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  matchScore: { fontSize: 16, fontWeight: '900', width: 24, textAlign: 'center' },
  matchDash: { fontSize: 12, color: '#1e2d45' },
  matchWinBadge: { flex: 1, paddingHorizontal: 8, paddingVertical: 3, borderRadius: 8, alignItems: 'flex-end' },
  matchWinTxt: { fontSize: 11, fontWeight: '800' },
});
