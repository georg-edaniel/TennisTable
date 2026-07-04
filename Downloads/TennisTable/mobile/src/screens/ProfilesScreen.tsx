import React, { useCallback, useRef, useState } from 'react';
import {
  Alert, FlatList, Image, Modal, ScrollView, StyleSheet, Text, TextInput,
  TouchableOpacity, View,
} from 'react-native';
import StatShareCard from '../components/StatShareCard';
import BadgeCelebrationModal from '../components/BadgeCelebrationModal';
import { useFocusEffect } from '@react-navigation/native';
import EmptyState from '../components/EmptyState';
import { Ionicons } from '@expo/vector-icons';
import * as ImagePicker from 'expo-image-picker';
import QRCode from 'react-native-qrcode-svg';
import { loadProfiles, createProfile, deleteProfile, updateProfile } from '../storage/profileStorage';
import { BG, CARD_BG, COLORS, PlayerProfile } from '../types';
import { getLevel, getLevelProgress, getITTFLevel, getITTFColor } from '../services/levelService';
import { getLoginStreakEmoji } from '../services/loginStreakService';
import { loadGoals, saveGoal, GoalRecord } from '../storage/goalStorage';
import { getEarnedBadges, getLockedBadges, BADGE_DEFS, BadgeDef } from '../services/badgeService';
import PlayerCard from '../components/PlayerCard';
import { CameraView, useCameraPermissions } from 'expo-camera';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { useNavigation } from '@react-navigation/native';

const ACCENT = '#6366f1';

export default function ProfilesScreen() {
  const [profiles, setProfiles] = useState<PlayerProfile[]>([]);
  const [addVisible, setAddVisible] = useState(false);
  const [newName, setNewName] = useState('');
  const [creating, setCreating] = useState(false);
  const [achProfile, setAchProfile] = useState<PlayerProfile | null>(null);
  const [qrProfile, setQrProfile] = useState<PlayerProfile | null>(null);
  const [scanVisible, setScanVisible] = useState(false);
  const [scanEnabled, setScanEnabled] = useState(true);
  const [goals, setGoals] = useState<GoalRecord[]>([]);
  const [goalEditProfile, setGoalEditProfile] = useState<PlayerProfile | null>(null);
  const [goalEloInput, setGoalEloInput] = useState('');
  const [goalMatchesInput, setGoalMatchesInput] = useState('');
  const [shareProfile, setShareProfile] = useState<PlayerProfile | null>(null);
  const [newBadges, setNewBadges] = useState<BadgeDef[]>([]);
  const [showBadgeCelebration, setShowBadgeCelebration] = useState(false);
  const profilesRef = useRef<PlayerProfile[]>([]);
  const navigation = useNavigation<any>();
  const [cameraPermission, requestCameraPermission] = useCameraPermissions();

  async function openScanner() {
    if (!cameraPermission?.granted) {
      const result = await requestCameraPermission();
      if (!result.granted) {
        Alert.alert('Permission refusée', 'Autorise la caméra pour scanner les défis QR.');
        return;
      }
    }
    setScanEnabled(true);
    setScanVisible(true);
  }

  async function handleScan(data: string) {
    if (!scanEnabled) return;
    setScanEnabled(false);
    try {
      const parsed = JSON.parse(data);
      if (parsed.type === 'challenge' && parsed.profileId) {
        await AsyncStorage.setItem('@tt_challenge', JSON.stringify(parsed));
        setScanVisible(false);
        navigation.navigate('Play' as never);
      }
    } catch {}
    setTimeout(() => setScanEnabled(true), 2000);
  }

  useFocusEffect(useCallback(() => {
    const oldBadgeMap = new Map(profilesRef.current.map(p => [p.id, getEarnedBadges(p).map(b => b.id)]));
    const wasLoaded = profilesRef.current.length > 0;

    loadProfiles().then(fresh => {
      const sorted = [...fresh].sort((a, b) => b.elo - a.elo);
      profilesRef.current = sorted;
      setProfiles(sorted);

      if (wasLoaded) {
        const earned: BadgeDef[] = [];
        for (const fp of fresh) {
          const oldIds = oldBadgeMap.get(fp.id) ?? [];
          getEarnedBadges(fp).forEach(b => { if (!oldIds.includes(b.id)) earned.push(b); });
        }
        if (earned.length > 0) { setNewBadges(earned); setShowBadgeCelebration(true); }
      }
    });
    loadGoals().then(setGoals);
  }, []));

  async function handleCreate() {
    const name = newName.trim();
    if (!name) return;
    setCreating(true);
    try {
      await createProfile(name);
      const updated = await loadProfiles();
      setProfiles([...updated].sort((a, b) => b.elo - a.elo));
      setNewName('');
      setAddVisible(false);
    } finally { setCreating(false); }
  }

  async function pickPhoto(profile: PlayerProfile) {
    const perm = await ImagePicker.requestMediaLibraryPermissionsAsync();
    if (!perm.granted) { Alert.alert('Permission refusée', 'Autorise l\'accès à la galerie.'); return; }
    const result = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ImagePicker.MediaTypeOptions.Images,
      allowsEditing: true,
      aspect: [1, 1],
      quality: 0.6,
      base64: false,
    });
    if (!result.canceled && result.assets[0]) {
      const updated = { ...profile, photoUri: result.assets[0].uri };
      await updateProfile(updated);
      setProfiles(prev => prev.map(p => p.id === profile.id ? updated : p));
    }
  }

  function handleDelete(profile: PlayerProfile) {
    Alert.alert(
      'Supprimer le profil',
      `Supprimer "${profile.name}" ? L'historique ELO sera perdu.`,
      [
        { text: 'Annuler', style: 'cancel' },
        { text: 'Supprimer', style: 'destructive', onPress: async () => {
          await deleteProfile(profile.id);
          setProfiles(prev => prev.filter(p => p.id !== profile.id));
        }},
      ]
    );
  }

  function renderItem({ item, index }: { item: PlayerProfile; index: number }) {
    const winRate = item.wins + item.losses > 0
      ? Math.round((item.wins / (item.wins + item.losses)) * 100)
      : 0;
    const podiumColors = ['#f59e0b', '#94a3b8', '#b45309'];
    const isPodium = index < 3;
    const level = getLevel(item.elo);
    const levelPct = getLevelProgress(item.elo);
    const earned = getEarnedBadges(item);
    const ittfLevel = getITTFLevel(item.elo);
    const ittfColor = getITTFColor(item.elo);
    const streakEmoji = getLoginStreakEmoji(item.loginStreak ?? 0);
    const profileGoal = goals.find(g => g.profileId === item.id);

    return (
      <View style={[s.card, isPodium && { borderColor: podiumColors[index] + '60' }]}>
        {/* Row 1: rank + photo + info + ELO + QR + delete */}
        <View style={s.cardRow}>
          <View style={[s.rankBox, isPodium && { backgroundColor: podiumColors[index] + '20' }]}>
            {isPodium
              ? <Ionicons name="trophy" size={14} color={podiumColors[index]} />
              : <Text style={s.rankNum}>#{index + 1}</Text>
            }
          </View>
          {/* Photo avatar */}
          <TouchableOpacity onPress={() => pickPhoto(item)}>
            {item.photoUri ? (
              <Image source={{ uri: item.photoUri }} style={s.avatar} />
            ) : (
              <View style={s.avatarPlaceholder}>
                <Ionicons name="camera-outline" size={16} color="#475569" />
              </View>
            )}
          </TouchableOpacity>
          <View style={s.info}>
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
              <Text style={s.name} numberOfLines={1}>{item.name}</Text>
              <Text style={{ fontSize: 14 }}>{level.emoji}</Text>
              <Text style={[s.levelName, { color: level.color }]}>{level.name}</Text>
              <Text style={[s.ittfLbl, { color: ittfColor }]}>{ittfLevel}</Text>
              {(item.loginStreak ?? 0) >= 7 && (
                <Text style={s.loginStreakTxt}>{streakEmoji} {item.loginStreak}j</Text>
              )}
            </View>
            <View style={s.subRow}>
              <Text style={s.wl}>{item.wins}V {item.losses}D</Text>
              {item.wins + item.losses > 0 && <>
                <Text style={s.sep}>·</Text>
                <Text style={s.wr}>{winRate}%</Text>
              </>}
              {item.currentStreak > 0 && <>
                <Text style={s.sep}>·</Text>
                <Text style={s.streakTxt}>🔥 {item.currentStreak}</Text>
              </>}
            </View>
          </View>
          <View style={s.eloBox}>
            <Text style={[s.elo, { color: level.color }]}>{item.elo}</Text>
            <Text style={s.eloLbl}>ELO</Text>
          </View>
          <TouchableOpacity style={s.qrBtn} onPress={() => setQrProfile(item)}>
            <Ionicons name="qr-code-outline" size={16} color="#38bdf8" />
          </TouchableOpacity>
          <TouchableOpacity style={s.qrBtn} onPress={() => setShareProfile(item)}>
            <Ionicons name="share-outline" size={16} color="#94a3b8" />
          </TouchableOpacity>
          <TouchableOpacity style={s.deleteBtn} onPress={() => handleDelete(item)}>
            <Ionicons name="trash-outline" size={16} color="#f87171" />
          </TouchableOpacity>
        </View>

        {/* Level progress bar */}
        <View style={s.lvlRow}>
          <View style={s.lvlTrack}>
            <View style={[s.lvlFill, { width: `${levelPct}%` as any, backgroundColor: level.color }]} />
          </View>
          <Text style={[s.lvlPct, { color: level.color }]}>{levelPct}%</Text>
        </View>

        {/* Earned badges row */}
        <View style={s.badgesRow}>
          {earned.slice(0, 5).map(b => (
            <View key={b.id} style={s.badgeChip}>
              <Text style={s.badgeEmoji}>{b.emoji}</Text>
            </View>
          ))}
          <TouchableOpacity style={s.trophiesBtn} onPress={() => setAchProfile(item)}>
            <Text style={s.trophiesTxt}>
              {earned.length > 0 ? `${earned.length} 🏅 →` : 'Voir objectifs →'}
            </Text>
          </TouchableOpacity>
        </View>

        {/* D1 – Personal goals (compact one-liner) */}
        <TouchableOpacity
          style={s.goalRow}
          onPress={() => {
            setGoalEditProfile(item);
            const g = goals.find(gg => gg.profileId === item.id);
            setGoalEloInput(g?.eloTarget ? String(g.eloTarget) : '');
            setGoalMatchesInput(g?.matchesPerWeek ? String(g.matchesPerWeek) : '');
          }}
        >
          <Ionicons name="flag-outline" size={12} color="#6366f1" />
          {profileGoal?.eloTarget ? (
            <>
              <Text style={s.goalChipTxt}>🎯 {item.elo}/{profileGoal.eloTarget}</Text>
              <View style={s.goalBar}>
                <View style={[s.goalFill, { width: `${Math.min(100, Math.round((item.elo / profileGoal.eloTarget) * 100))}%` as any }]} />
              </View>
              <Text style={s.goalPct}>{Math.min(100, Math.round((item.elo / profileGoal.eloTarget) * 100))}%</Text>
            </>
          ) : (
            <Text style={s.goalAdd}>Définir un objectif</Text>
          )}
          {profileGoal?.matchesPerWeek ? (
            <Text style={s.goalChipTxt}>  📅 {profileGoal.matchesPerWeek}/sem</Text>
          ) : null}
        </TouchableOpacity>
      </View>
    );
  }

  // Achievements modal
  const earnedAch = achProfile ? getEarnedBadges(achProfile) : [];
  const lockedAch = achProfile ? getLockedBadges(achProfile) : [];

  return (
    <View style={s.root}>
      {/* Header */}
      <View style={s.header}>
        <View>
          <Text style={s.title}>Profils</Text>
          <Text style={s.subtitle}>{profiles.length} joueur{profiles.length !== 1 ? 's' : ''}</Text>
        </View>
        <View style={{ flexDirection: 'row', gap: 8, alignItems: 'center' }}>
          <TouchableOpacity style={s.scanBtn} onPress={openScanner}>
            <Ionicons name="scan-outline" size={18} color={ACCENT} />
          </TouchableOpacity>
          <TouchableOpacity style={s.addBtn} onPress={() => setAddVisible(true)}>
            <Ionicons name="add" size={18} color="#fff" />
            <Text style={s.addTxt}>Nouveau</Text>
          </TouchableOpacity>
        </View>
      </View>

      {profiles.length === 0 ? (
        <EmptyState
          icon="person-outline"
          title="Aucun profil créé"
          subtitle="Crée un profil joueur pour suivre ton ELO, tes badges et ton niveau ITTF"
          actionLabel="+ Créer un profil"
          onAction={() => setAddVisible(true)}
        />
      ) : (
        <FlatList
          data={profiles}
          keyExtractor={p => p.id}
          renderItem={renderItem}
          contentContainerStyle={s.list}
          showsVerticalScrollIndicator={false}
        />
      )}

      {/* Modal créer profil */}
      <Modal visible={addVisible} transparent animationType="slide">
        <View style={s.overlay}>
          <View style={s.modal}>
            <Text style={s.modalTitle}>Nouveau profil</Text>
            <TextInput
              style={s.input}
              value={newName}
              onChangeText={setNewName}
              placeholder="Nom du joueur"
              placeholderTextColor="#475569"
              autoFocus maxLength={20}
              returnKeyType="done"
              onSubmitEditing={handleCreate}
            />
            <TouchableOpacity
              style={[s.createBtn, (!newName.trim() || creating) && s.createBtnDisabled]}
              onPress={handleCreate}
              disabled={!newName.trim() || creating}
            >
              <Text style={s.createBtnTxt}>{creating ? 'Création…' : 'Créer (ELO 1200)'}</Text>
            </TouchableOpacity>
            <TouchableOpacity style={s.cancelBtn} onPress={() => { setAddVisible(false); setNewName(''); }}>
              <Text style={s.cancelTxt}>Annuler</Text>
            </TouchableOpacity>
          </View>
        </View>
      </Modal>

      {/* D1 – Goal edit modal */}
      <Modal visible={goalEditProfile !== null} transparent animationType="slide">
        <View style={s.overlay}>
          <View style={s.modal}>
            <Text style={s.modalTitle}>🎯 Objectifs — {goalEditProfile?.name}</Text>
            <Text style={s.input_label}>ELO cible</Text>
            <TextInput
              style={s.input}
              value={goalEloInput}
              onChangeText={setGoalEloInput}
              placeholder="ex. 1500"
              placeholderTextColor="#475569"
              keyboardType="numeric"
              maxLength={5}
            />
            <Text style={s.input_label}>Matchs / semaine</Text>
            <TextInput
              style={s.input}
              value={goalMatchesInput}
              onChangeText={setGoalMatchesInput}
              placeholder="ex. 3"
              placeholderTextColor="#475569"
              keyboardType="numeric"
              maxLength={2}
            />
            <TouchableOpacity
              style={s.createBtn}
              onPress={async () => {
                if (!goalEditProfile) return;
                const goal: GoalRecord = {
                  profileId: goalEditProfile.id,
                  eloTarget: goalEloInput ? parseInt(goalEloInput, 10) : undefined,
                  matchesPerWeek: goalMatchesInput ? parseInt(goalMatchesInput, 10) : undefined,
                };
                await saveGoal(goal);
                setGoals(await loadGoals());
                setGoalEditProfile(null);
              }}
            >
              <Text style={s.createBtnTxt}>Sauvegarder</Text>
            </TouchableOpacity>
            <TouchableOpacity style={s.cancelBtn} onPress={() => setGoalEditProfile(null)}>
              <Text style={s.cancelTxt}>Annuler</Text>
            </TouchableOpacity>
          </View>
        </View>
      </Modal>

      {/* Achievements modal */}
      <Modal visible={achProfile !== null} transparent animationType="slide">
        <View style={s.overlay}>
          <View style={[s.modal, { maxHeight: '85%' }]}>
            <View style={{ flexDirection: 'row', alignItems: 'center', marginBottom: 4 }}>
              <Text style={[s.modalTitle, { flex: 1, textAlign: 'left' }]}>
                Trophées – {achProfile?.name}
              </Text>
              <TouchableOpacity onPress={() => setAchProfile(null)}>
                <Ionicons name="close" size={22} color="#94a3b8" />
              </TouchableOpacity>
            </View>
            <ScrollView showsVerticalScrollIndicator={false}>
              {earnedAch.length > 0 && (
                <>
                  <Text style={ach.section}>Débloqués ({earnedAch.length})</Text>
                  {earnedAch.map(b => <BadgeRow key={b.id} badge={b} earned />)}
                </>
              )}
              {lockedAch.length > 0 && (
                <>
                  <Text style={[ach.section, { marginTop: 14 }]}>À débloquer ({lockedAch.length})</Text>
                  {lockedAch.map(b => <BadgeRow key={b.id} badge={b} earned={false} />)}
                </>
              )}
            </ScrollView>
            <TouchableOpacity style={s.cancelBtn} onPress={() => setAchProfile(null)}>
              <Text style={s.cancelTxt}>Fermer</Text>
            </TouchableOpacity>
          </View>
        </View>
      </Modal>

      {/* Scanner QR adversaire */}
      <Modal visible={scanVisible} transparent animationType="slide">
        <View style={[s.overlay, { justifyContent: 'flex-end' }]}>
          <View style={[s.modal, { height: '72%', padding: 0, overflow: 'hidden' }]}>
            <View style={{ padding: 16, flexDirection: 'row', alignItems: 'center', gap: 8 }}>
              <Text style={[s.modalTitle, { flex: 1, textAlign: 'left' }]}>📲 Scanner un défi</Text>
              <TouchableOpacity onPress={() => setScanVisible(false)}>
                <Ionicons name="close" size={22} color="#94a3b8" />
              </TouchableOpacity>
            </View>
            {scanVisible && (
              <CameraView
                style={{ flex: 1 }}
                facing="back"
                barcodeScannerSettings={{ barcodeTypes: ['qr'] }}
                onBarcodeScanned={({ data }) => handleScan(data)}
              />
            )}
            <View style={{ padding: 14 }}>
              <Text style={{ fontSize: 12, color: '#64748b', textAlign: 'center' }}>
                Scanne le QR code d'un profil pour lancer un défi → onglet Jouer
              </Text>
            </View>
          </View>
        </View>
      </Modal>

      {/* Badge Celebration */}
      {showBadgeCelebration && newBadges.length > 0 && (
        <BadgeCelebrationModal
          badges={newBadges}
          onClose={() => { setShowBadgeCelebration(false); setNewBadges([]); }}
        />
      )}

      {/* Share Stats modal */}
      {shareProfile && (
        <Modal visible transparent animationType="fade">
          <StatShareCard profile={shareProfile} onClose={() => setShareProfile(null)} />
        </Modal>
      )}

      {/* QR Code modal */}
      <Modal visible={qrProfile !== null} transparent animationType="fade">
        <View style={s.overlay}>
          <View style={[s.modal, { alignItems: 'center', gap: 16 }]}>
            <Text style={s.modalTitle}>📲 {qrProfile?.name}</Text>
            <View style={{ backgroundColor: '#fff', padding: 16, borderRadius: 16 }}>
              {qrProfile && (
                <QRCode
                  value={JSON.stringify({ type: 'challenge', profileId: qrProfile.id, name: qrProfile.name, elo: qrProfile.elo })}
                  size={200}
                />
              )}
            </View>
            <Text style={{ fontSize: 12, color: '#64748b', textAlign: 'center' }}>
              ELO {qrProfile?.elo} · {qrProfile?.wins}V {qrProfile?.losses}D
            </Text>
            <TouchableOpacity style={s.cancelBtn} onPress={() => setQrProfile(null)}>
              <Text style={s.cancelTxt}>Fermer</Text>
            </TouchableOpacity>
          </View>
        </View>
      </Modal>
    </View>
  );
}

function BadgeRow({ badge, earned }: { badge: BadgeDef; earned: boolean }) {
  return (
    <View style={[ach.row, !earned && { opacity: 0.35 }]}>
      <View style={ach.iconBox}>
        <Text style={ach.icon}>{badge.emoji}</Text>
      </View>
      <View style={ach.info}>
        <Text style={ach.name}>{badge.name}</Text>
        <Text style={ach.desc}>{badge.description}</Text>
      </View>
      {earned && <Ionicons name="checkmark-circle" size={18} color="#4ade80" />}
    </View>
  );
}

const ach = StyleSheet.create({
  section: { fontSize: 11, fontWeight: '700', color: '#64748b', textTransform: 'uppercase', letterSpacing: 0.8, marginBottom: 8 },
  row: { flexDirection: 'row', alignItems: 'center', gap: 12, paddingVertical: 8, borderBottomWidth: 1, borderBottomColor: '#1e2d45' },
  iconBox: { width: 36, height: 36, borderRadius: 18, backgroundColor: '#1e2d45', alignItems: 'center', justifyContent: 'center' },
  icon: { fontSize: 18 },
  info: { flex: 1 },
  name: { fontSize: 14, fontWeight: '700', color: '#f1f5f9' },
  desc: { fontSize: 11, color: '#64748b', marginTop: 2 },
});

const s = StyleSheet.create({
  root: { flex: 1, backgroundColor: BG },
  header: {
    flexDirection: 'row', alignItems: 'flex-end', justifyContent: 'space-between',
    paddingHorizontal: 20, paddingTop: 20, paddingBottom: 12,
  },
  title: { fontSize: 26, fontWeight: '900', color: '#f1f5f9' },
  subtitle: { fontSize: 12, color: '#475569', marginTop: 2 },
  addBtn: { flexDirection: 'row', alignItems: 'center', gap: 5, backgroundColor: ACCENT, borderRadius: 12, paddingHorizontal: 14, paddingVertical: 8 },
  addTxt: { color: '#fff', fontSize: 13, fontWeight: '700' },
  scanBtn: { width: 38, height: 38, borderRadius: 12, borderWidth: 1.5, borderColor: ACCENT + '60', backgroundColor: ACCENT + '15', alignItems: 'center', justifyContent: 'center' },

  list: { paddingHorizontal: 16, paddingBottom: 24, gap: 10 },

  card: { backgroundColor: CARD_BG, borderRadius: 18, padding: 14, gap: 8, borderWidth: 1, borderColor: '#1e2d45' },
  cardRow: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  rankBox: { width: 32, height: 32, borderRadius: 16, backgroundColor: '#1e2d45', alignItems: 'center', justifyContent: 'center' },
  rankNum: { fontSize: 11, color: '#64748b', fontWeight: '800' },
  info: { flex: 1 },
  name: { fontSize: 15, fontWeight: '800', color: '#f1f5f9' },
  levelName: { fontSize: 11, fontWeight: '700' },
  subRow: { flexDirection: 'row', alignItems: 'center', gap: 5, marginTop: 2 },
  wl: { fontSize: 11, color: '#64748b', fontWeight: '600' },
  sep: { fontSize: 11, color: '#334155' },
  wr: { fontSize: 11, color: '#94a3b8', fontWeight: '600' },
  streakTxt: { fontSize: 11, fontWeight: '700', color: '#f59e0b' },
  eloBox: { alignItems: 'center' },
  elo: { fontSize: 20, fontWeight: '900' },
  eloLbl: { fontSize: 9, color: '#475569', fontWeight: '700', letterSpacing: 1 },
  deleteBtn: { padding: 6, borderRadius: 8, backgroundColor: '#7f1d1d15', borderWidth: 1, borderColor: '#7f1d1d40' },
  qrBtn: { padding: 6, borderRadius: 8, backgroundColor: '#38bdf815', borderWidth: 1, borderColor: '#38bdf840' },
  avatar: { width: 36, height: 36, borderRadius: 18 },
  avatarPlaceholder: { width: 36, height: 36, borderRadius: 18, backgroundColor: '#1e2d45', alignItems: 'center', justifyContent: 'center', borderWidth: 1, borderColor: '#2d3f5a' },

  lvlRow: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  lvlTrack: { flex: 1, height: 6, backgroundColor: '#1e2d45', borderRadius: 3, overflow: 'hidden' },
  lvlFill: { height: '100%', borderRadius: 3 },
  lvlPct: { fontSize: 11, fontWeight: '800', width: 30, textAlign: 'right' },

  badgesRow: { flexDirection: 'row', alignItems: 'center', flexWrap: 'wrap', gap: 6 },
  badgeChip: { width: 28, height: 28, borderRadius: 14, backgroundColor: '#1e2d45', alignItems: 'center', justifyContent: 'center' },
  badgeEmoji: { fontSize: 14 },
  trophiesBtn: { marginLeft: 4 },
  trophiesTxt: { fontSize: 11, color: ACCENT, fontWeight: '700' },
  noTrophies: { flexDirection: 'row', alignItems: 'center', gap: 4 },
  noTrophiesTxt: { fontSize: 11, color: '#334155', fontStyle: 'italic' },

  empty: { flex: 1, alignItems: 'center', justifyContent: 'center', gap: 12, padding: 32 },
  emptyIcon: { width: 80, height: 80, borderRadius: 40, backgroundColor: ACCENT + '15', alignItems: 'center', justifyContent: 'center' },
  emptyTxt: { fontSize: 17, color: '#f1f5f9', fontWeight: '700' },
  emptyHint: { fontSize: 13, color: '#64748b', textAlign: 'center' },

  overlay: { flex: 1, backgroundColor: 'rgba(0,0,0,0.85)', alignItems: 'center', justifyContent: 'center', padding: 24 },
  modal: { width: '100%', backgroundColor: CARD_BG, borderRadius: 24, padding: 24, gap: 14, borderWidth: 1, borderColor: '#1e2d45' },
  modalTitle: { fontSize: 20, fontWeight: '900', color: '#f1f5f9', textAlign: 'center' },
  input: { borderWidth: 1.5, borderColor: '#1e2d45', borderRadius: 12, paddingHorizontal: 14, paddingVertical: 12, color: '#f1f5f9', fontSize: 15, fontWeight: '600', backgroundColor: '#0a0f1e' },
  createBtn: { backgroundColor: ACCENT, borderRadius: 14, paddingVertical: 14, alignItems: 'center' },
  createBtnDisabled: { opacity: 0.5 },
  createBtnTxt: { color: '#fff', fontSize: 15, fontWeight: '800' },
  cancelBtn: { alignItems: 'center', paddingVertical: 4 },
  cancelTxt: { color: '#475569', fontSize: 13, textDecorationLine: 'underline' },

  loginStreakTxt: { fontSize: 10, fontWeight: '700', color: '#f59e0b' },
  ittfLbl: { fontSize: 10, fontWeight: '600', paddingHorizontal: 5, paddingVertical: 2, borderRadius: 4, backgroundColor: '#1e2d45' },

  goalRow: { flexDirection: 'row', alignItems: 'center', gap: 6, paddingTop: 6, borderTopWidth: 1, borderTopColor: '#1e2d45' },
  goalLbl: { fontSize: 11, fontWeight: '700', color: '#64748b' },
  goalChip: { flexDirection: 'row', alignItems: 'center', gap: 4 },
  goalChipTxt: { fontSize: 10, color: '#94a3b8', fontWeight: '600' },
  goalBar: { width: 50, height: 4, backgroundColor: '#1e2d45', borderRadius: 2, overflow: 'hidden' },
  goalFill: { height: '100%', backgroundColor: ACCENT, borderRadius: 2 },
  goalPct: { fontSize: 10, color: '#64748b', fontWeight: '700' },
  goalAdd: { fontSize: 10, color: ACCENT, fontWeight: '600' },

  input_label: { fontSize: 12, fontWeight: '700', color: '#64748b', textTransform: 'uppercase', letterSpacing: 0.8, marginBottom: 4 },
});
