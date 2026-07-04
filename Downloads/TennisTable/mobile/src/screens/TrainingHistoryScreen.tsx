import React, { useCallback, useState } from 'react';
import { Alert, FlatList, StyleSheet, Text, TouchableOpacity, View } from 'react-native';
import { useFocusEffect } from '@react-navigation/native';
import { Ionicons } from '@expo/vector-icons';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { loadTrainingSessions } from '../storage/trainingStorage';
import { loadProfiles } from '../storage/profileStorage';
import { BG, CARD_BG, STROKES, TrainingSession, PlayerProfile } from '../types';

const ACCENT = '#6366f1';

function fmtDate(iso: string) {
  return new Date(iso).toLocaleDateString('fr-FR', { day: '2-digit', month: 'short' });
}
function fmtDuration(secs: number) {
  return `${Math.floor(secs / 60)}m ${String(secs % 60).padStart(2, '0')}s`;
}

export default function TrainingHistoryScreen() {
  const [sessions, setSessions] = useState<TrainingSession[]>([]);
  const [profiles, setProfiles] = useState<PlayerProfile[]>([]);
  const [loadError, setLoadError] = useState(false);

  useFocusEffect(useCallback(() => {
    setLoadError(false);
    Promise.all([loadTrainingSessions(), loadProfiles()])
      .then(([s, p]) => {
        setSessions(s);
        setProfiles(p);
      })
      .catch(() => setLoadError(true));
  }, []));

  function profileName(id: string | null) {
    if (!id) return '—';
    return profiles.find(p => p.id === id)?.name ?? '—';
  }

  // Stats by stroke
  const strokeStats = STROKES.map(st => ({
    ...st,
    total: sessions.filter(s => s.stroke === st.name).reduce((acc, s) => acc + s.completed, 0),
    sessions: sessions.filter(s => s.stroke === st.name).length,
  }));
  const maxTotal = Math.max(...strokeStats.map(s => s.total), 1);

  async function handleClear() {
    Alert.alert('Effacer', 'Supprimer tout l\'historique d\'entraînement ?', [
      { text: 'Annuler', style: 'cancel' },
      { text: 'Effacer', style: 'destructive', onPress: async () => {
        await AsyncStorage.removeItem('@tt_trainings');
        setSessions([]);
      }},
    ]);
  }

  if (loadError) {
    return (
      <View style={[s.root, { alignItems: 'center', justifyContent: 'center', gap: 12 }]}>
        <Text style={{ fontSize: 36 }}>⚠️</Text>
        <Text style={{ fontSize: 16, fontWeight: '800', color: '#f87171' }}>Erreur de chargement</Text>
        <Text style={{ fontSize: 13, color: '#64748b', textAlign: 'center', paddingHorizontal: 32 }}>
          Impossible de lire l'historique d'entraînement. Vérifie le stockage de l'appareil.
        </Text>
      </View>
    );
  }

  return (
    <View style={s.root}>
      <View style={s.header}>
        <View>
          <Text style={s.title}>Entraînements</Text>
          <Text style={s.subtitle}>{sessions.length} séance{sessions.length !== 1 ? 's' : ''}</Text>
        </View>
        {sessions.length > 0 && (
          <TouchableOpacity style={s.clearBtn} onPress={handleClear}>
            <Ionicons name="trash-outline" size={14} color="#f87171" />
            <Text style={s.clearTxt}>Effacer</Text>
          </TouchableOpacity>
        )}
      </View>

      {sessions.length === 0 ? (
        <View style={s.empty}>
          <View style={s.emptyIcon}><Ionicons name="fitness-outline" size={40} color={ACCENT} /></View>
          <Text style={s.emptyTxt}>Aucune séance</Text>
          <Text style={s.emptyHint}>Lance un entraînement depuis l'onglet Jouer</Text>
        </View>
      ) : (
        <FlatList
          data={[{ type: 'stats' as const }, ...sessions.map(s => ({ type: 'session' as const, session: s }))]}
          keyExtractor={(item, i) => item.type === 'stats' ? 'stats' : (item as any).session.id}
          showsVerticalScrollIndicator={false}
          contentContainerStyle={s.list}
          renderItem={({ item }) => {
            if (item.type === 'stats') {
              return (
                <View style={s.card}>
                  <View style={s.cardHeader}>
                    <Ionicons name="bar-chart-outline" size={16} color="#64748b" />
                    <Text style={s.cardTitle}>Stats par coup</Text>
                  </View>
                  {strokeStats.filter(st => st.total > 0).map(st => (
                    <View key={st.name} style={st2.row}>
                      <Text style={st2.emoji}>{st.emoji}</Text>
                      <Text style={st2.name}>{st.name}</Text>
                      <View style={st2.track}>
                        <View style={[st2.fill, { width: `${Math.round((st.total / maxTotal) * 100)}%` as any, backgroundColor: st.color + 'cc' }]} />
                      </View>
                      <Text style={[st2.total, { color: st.color }]}>{st.total}</Text>
                      <Text style={st2.sess}>{st.sessions}x</Text>
                    </View>
                  ))}
                  {strokeStats.every(st => st.total === 0) && (
                    <Text style={{ color: '#475569', fontSize: 12 }}>Aucune frappe enregistrée</Text>
                  )}
                </View>
              );
            }

            const sess = (item as any).session as TrainingSession;
            const stroke = STROKES.find(s => s.name === sess.stroke);
            const pct = sess.target > 0 ? Math.round((sess.completed / sess.target) * 100) : 0;
            const done = sess.completed >= sess.target;

            return (
              <View style={s.card}>
                <View style={s.cardTop}>
                  <View style={[s.strokeIcon, { backgroundColor: (stroke?.color ?? ACCENT) + '20' }]}>
                    <Text style={{ fontSize: 18 }}>{stroke?.emoji ?? '🏓'}</Text>
                  </View>
                  <View style={{ flex: 1 }}>
                    <Text style={s.strokeName}>{sess.stroke}</Text>
                    <Text style={s.sessionMeta}>
                      {profileName(sess.profileId)} · {fmtDate(sess.date)} · {fmtDuration(sess.durationSecs)}
                    </Text>
                  </View>
                  {done && (
                    <View style={s.doneBadge}>
                      <Ionicons name="checkmark-circle" size={14} color="#4ade80" />
                      <Text style={s.doneTxt}>100%</Text>
                    </View>
                  )}
                </View>
                <View style={s.progressRow}>
                  <View style={s.progressTrack}>
                    <View style={[s.progressFill, {
                      width: `${Math.min(pct, 100)}%` as any,
                      backgroundColor: done ? '#4ade80' : (stroke?.color ?? ACCENT),
                    }]} />
                  </View>
                  <Text style={[s.progressPct, { color: done ? '#4ade80' : (stroke?.color ?? ACCENT) }]}>
                    {sess.completed}/{sess.target}
                  </Text>
                </View>
              </View>
            );
          }}
        />
      )}
    </View>
  );
}

const s = StyleSheet.create({
  root: { flex: 1, backgroundColor: BG },
  header: { flexDirection: 'row', alignItems: 'flex-end', justifyContent: 'space-between', paddingHorizontal: 20, paddingTop: 20, paddingBottom: 12 },
  title: { fontSize: 26, fontWeight: '900', color: '#f1f5f9' },
  subtitle: { fontSize: 12, color: '#475569', marginTop: 2 },
  clearBtn: { flexDirection: 'row', alignItems: 'center', gap: 4, borderWidth: 1, borderColor: '#7f1d1d50', backgroundColor: '#7f1d1d15', borderRadius: 10, paddingHorizontal: 12, paddingVertical: 6 },
  clearTxt: { color: '#f87171', fontSize: 13, fontWeight: '600' },
  list: { paddingHorizontal: 16, paddingBottom: 24, gap: 10 },
  card: { backgroundColor: CARD_BG, borderRadius: 18, padding: 14, gap: 10, borderWidth: 1, borderColor: '#1e2d45' },
  cardHeader: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  cardTitle: { fontSize: 12, fontWeight: '700', color: '#64748b', textTransform: 'uppercase', letterSpacing: 0.8 },
  cardTop: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  strokeIcon: { width: 40, height: 40, borderRadius: 20, alignItems: 'center', justifyContent: 'center' },
  strokeName: { fontSize: 14, fontWeight: '800', color: '#f1f5f9' },
  sessionMeta: { fontSize: 11, color: '#64748b', marginTop: 2 },
  doneBadge: { flexDirection: 'row', alignItems: 'center', gap: 4, backgroundColor: '#4ade8020', borderWidth: 1, borderColor: '#4ade8040', borderRadius: 8, paddingHorizontal: 8, paddingVertical: 3 },
  doneTxt: { fontSize: 11, color: '#4ade80', fontWeight: '800' },
  progressRow: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  progressTrack: { flex: 1, height: 8, backgroundColor: '#1e2d45', borderRadius: 4, overflow: 'hidden' },
  progressFill: { height: '100%', borderRadius: 4 },
  progressPct: { fontSize: 12, fontWeight: '800', minWidth: 40, textAlign: 'right' },
  empty: { flex: 1, alignItems: 'center', justifyContent: 'center', gap: 12, padding: 32 },
  emptyIcon: { width: 80, height: 80, borderRadius: 40, backgroundColor: ACCENT + '15', alignItems: 'center', justifyContent: 'center' },
  emptyTxt: { fontSize: 17, color: '#f1f5f9', fontWeight: '700' },
  emptyHint: { fontSize: 13, color: '#64748b', textAlign: 'center' },
});

const st2 = StyleSheet.create({
  row: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  emoji: { fontSize: 14, width: 20, textAlign: 'center' },
  name: { fontSize: 11, color: '#94a3b8', width: 68 },
  track: { flex: 1, height: 8, backgroundColor: '#1e2d45', borderRadius: 4, overflow: 'hidden' },
  fill: { height: '100%', borderRadius: 4 },
  total: { fontSize: 13, fontWeight: '800', width: 36, textAlign: 'right' },
  sess: { fontSize: 10, color: '#475569', width: 24 },
});
