import React, { useEffect, useState } from 'react';
import {
  ActivityIndicator, Alert, ScrollView, StyleSheet, Text,
  TextInput, TouchableOpacity, View,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import AsyncStorage from '@react-native-async-storage/async-storage';
import {
  getApiUrl, setApiUrl, login, register, logout,
  isLoggedIn, testConnection, syncMatch, flushSyncQueue, getSyncQueue,
} from '../services/apiService';
import { loadMatches } from '../storage/matchStorage';
import { BG, CARD_BG } from '../types';

const ACCENT = '#6366f1';
const LAST_SYNC_KEY = '@tt_last_sync';

export default function CloudSyncScreen() {
  const [apiUrl, setApiUrlState] = useState('https://tennistable.onrender.com');
  const [username, setUsername] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [isRegistering, setIsRegistering] = useState(false);
  const [loggedIn, setLoggedIn] = useState(false);
  const [loading, setLoading] = useState(false);
  const [testing, setTesting] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [connectionOk, setConnectionOk] = useState<boolean | null>(null);
  const [lastSync, setLastSync] = useState<string | null>(null);
  const [syncResult, setSyncResult] = useState<string | null>(null);
  const [queueCount, setQueueCount] = useState(0);

  useEffect(() => {
    (async () => {
      const url = await getApiUrl();
      setApiUrlState(url);
      setLoggedIn(await isLoggedIn());
      const ls = await AsyncStorage.getItem(LAST_SYNC_KEY);
      setLastSync(ls);
      const q = await getSyncQueue();
      setQueueCount(q.length);
    })();
  }, []);

  async function handleTest() {
    setTesting(true);
    setConnectionOk(null);
    await setApiUrl(apiUrl);
    const ok = await testConnection();
    setConnectionOk(ok);
    setTesting(false);
    if (!ok) Alert.alert('Connexion échouée', 'Vérifie l\'URL et que le serveur est démarré.');
  }

  async function handleLogin() {
    if (!username.trim() || !password.trim()) {
      Alert.alert('Champs requis', 'Saisis un nom d\'utilisateur et un mot de passe.');
      return;
    }
    setLoading(true);
    await setApiUrl(apiUrl);
    const { ok, error } = await login(username.trim(), password.trim());
    setLoading(false);
    if (ok) {
      setLoggedIn(true);
      setPassword('');
    } else {
      Alert.alert('Connexion échouée', error ?? 'Identifiants incorrects');
    }
  }

  async function handleRegister() {
    if (!username.trim() || !password.trim() || !email.trim()) {
      Alert.alert('Champs requis', 'Saisis un nom d\'utilisateur, un email et un mot de passe.');
      return;
    }
    setLoading(true);
    await setApiUrl(apiUrl);
    const { ok, error } = await register(username.trim(), password.trim(), email.trim());
    setLoading(false);
    if (ok) {
      setLoggedIn(true);
      setPassword('');
      setIsRegistering(false);
    } else {
      Alert.alert('Inscription échouée', error ?? 'Essaie un autre nom d\'utilisateur');
    }
  }

  async function handleLogout() {
    await logout();
    setLoggedIn(false);
    setSyncResult(null);
  }

  async function handleSync() {
    if (!loggedIn) {
      Alert.alert('Non connecté', 'Connecte-toi d\'abord.');
      return;
    }
    setSyncing(true);
    setSyncResult(null);
    try {
      const matches = await loadMatches();
      let ok = 0, fail = 0;
      for (const m of matches) {
        const res = await syncMatch({
          opponent_name: m.player2 || 'Adversaire',
          p1_sets: m.score1 ?? 0,
          p2_sets: m.score2 ?? 0,
          notes: `vs ${m.player2} | ${m.durationSecs}s | win: ${m.winner === 0 ? m.player1 : m.player2}`,
          played_at: m.date,
        });
        if (res.ok) ok++;
        else fail++;
      }
      const now = new Date().toLocaleString('fr-FR');
      await AsyncStorage.setItem(LAST_SYNC_KEY, now);
      setLastSync(now);
      setSyncResult(`✅ ${ok} matchs synchronisés${fail > 0 ? ` (${fail} erreurs)` : ''}`);
    } catch (e: any) {
      setSyncResult(`❌ Erreur : ${e.message ?? 'Sync échouée'}`);
    }
    setSyncing(false);
  }

  return (
    <ScrollView style={s.root} contentContainerStyle={s.content} showsVerticalScrollIndicator={false}>
      <View style={s.header}>
        <Text style={s.title}>☁️ Cloud Sync</Text>
        <Text style={s.subtitle}>Synchronise tes matchs avec le serveur</Text>
      </View>

      {/* Server URL */}
      <View style={s.card}>
        <View style={s.cardHeader}>
          <Ionicons name="server-outline" size={14} color={ACCENT} />
          <Text style={s.cardTitle}>SERVEUR</Text>
        </View>
        <TextInput
          style={s.input}
          value={apiUrl}
          onChangeText={setApiUrlState}
          placeholder="http://localhost:8000"
          placeholderTextColor="#475569"
          autoCapitalize="none"
          autoCorrect={false}
          keyboardType="url"
        />
        <TouchableOpacity style={s.testBtn} onPress={handleTest} disabled={testing}>
          {testing
            ? <ActivityIndicator color={ACCENT} size="small" />
            : <>
                <Ionicons name="wifi-outline" size={14} color={ACCENT} />
                <Text style={s.testBtnTxt}>Tester la connexion</Text>
              </>
          }
        </TouchableOpacity>
        {connectionOk !== null && (
          <View style={[s.connBadge, connectionOk ? s.connOk : s.connFail]}>
            <Ionicons name={connectionOk ? 'checkmark-circle' : 'close-circle'} size={14}
              color={connectionOk ? '#4ade80' : '#f87171'} />
            <Text style={[s.connTxt, { color: connectionOk ? '#4ade80' : '#f87171' }]}>
              {connectionOk ? 'Serveur accessible' : 'Serveur inaccessible'}
            </Text>
          </View>
        )}
      </View>

      {/* Auth */}
      {loggedIn ? (
        <View style={s.card}>
          <View style={s.cardHeader}>
            <Ionicons name="person-circle-outline" size={14} color="#4ade80" />
            <Text style={s.cardTitle}>CONNECTÉ</Text>
          </View>
          <View style={s.connectedRow}>
            <Ionicons name="checkmark-circle" size={20} color="#4ade80" />
            <Text style={s.connectedTxt}>Compte actif</Text>
          </View>
          <TouchableOpacity style={s.logoutBtn} onPress={handleLogout}>
            <Ionicons name="log-out-outline" size={14} color="#94a3b8" />
            <Text style={s.logoutTxt}>Se déconnecter</Text>
          </TouchableOpacity>
        </View>
      ) : (
        <View style={s.card}>
          <View style={s.cardHeader}>
            <Ionicons name="lock-closed-outline" size={14} color={ACCENT} />
            <Text style={s.cardTitle}>{isRegistering ? 'CRÉER UN COMPTE' : 'CONNEXION'}</Text>
          </View>
          <TextInput
            style={s.input}
            value={username}
            onChangeText={setUsername}
            placeholder="Nom d'utilisateur"
            placeholderTextColor="#475569"
            autoCapitalize="none"
            autoCorrect={false}
          />
          {isRegistering && (
            <TextInput
              style={s.input}
              value={email}
              onChangeText={setEmail}
              placeholder="Email"
              placeholderTextColor="#475569"
              autoCapitalize="none"
              autoCorrect={false}
              keyboardType="email-address"
            />
          )}
          <TextInput
            style={s.input}
            value={password}
            onChangeText={setPassword}
            placeholder="Mot de passe (8+ car., lettre + chiffre)"
            placeholderTextColor="#475569"
            secureTextEntry
          />
          {isRegistering ? (
            <View style={s.authRow}>
              <TouchableOpacity style={[s.authBtn, { backgroundColor: ACCENT }]} onPress={handleRegister} disabled={loading}>
                {loading ? <ActivityIndicator color="#fff" size="small" />
                  : <Text style={s.authBtnTxt}>Créer le compte</Text>}
              </TouchableOpacity>
              <TouchableOpacity style={[s.authBtn, s.authBtnSecondary]} onPress={() => setIsRegistering(false)} disabled={loading}>
                <Text style={[s.authBtnTxt, { color: ACCENT }]}>Annuler</Text>
              </TouchableOpacity>
            </View>
          ) : (
            <View style={s.authRow}>
              <TouchableOpacity style={[s.authBtn, { backgroundColor: ACCENT }]} onPress={handleLogin} disabled={loading}>
                {loading ? <ActivityIndicator color="#fff" size="small" />
                  : <Text style={s.authBtnTxt}>Se connecter</Text>}
              </TouchableOpacity>
              <TouchableOpacity style={[s.authBtn, s.authBtnSecondary]} onPress={() => setIsRegistering(true)} disabled={loading}>
                <Text style={[s.authBtnTxt, { color: ACCENT }]}>Créer un compte</Text>
              </TouchableOpacity>
            </View>
          )}
        </View>
      )}

      {/* Sync */}
      <View style={s.card}>
        <View style={s.cardHeader}>
          <Ionicons name="sync-outline" size={14} color={ACCENT} />
          <Text style={s.cardTitle}>SYNCHRONISATION</Text>
        </View>
        {lastSync && (
          <View style={s.lastSyncRow}>
            <Ionicons name="time-outline" size={12} color="#64748b" />
            <Text style={s.lastSyncTxt}>Dernière sync : {lastSync}</Text>
          </View>
        )}
        {syncResult && (
          <View style={s.syncResultRow}>
            <Text style={s.syncResultTxt}>{syncResult}</Text>
          </View>
        )}
        <TouchableOpacity
          style={[s.syncBtn, (!loggedIn || syncing) && { opacity: 0.5 }]}
          onPress={handleSync}
          disabled={!loggedIn || syncing}
        >
          {syncing
            ? <ActivityIndicator color="#fff" size="small" />
            : <>
                <Ionicons name="cloud-upload-outline" size={16} color="#fff" />
                <Text style={s.syncBtnTxt}>Synchroniser maintenant</Text>
              </>
          }
        </TouchableOpacity>
        <Text style={s.syncHint}>
          Upload tous tes matchs locaux vers le serveur configuré ci-dessus.
          Les échecs sont mis en file d'attente et réessayés automatiquement.
        </Text>
        {queueCount > 0 && (
          <View style={s.queueRow}>
            <Ionicons name="time-outline" size={13} color="#f59e0b" />
            <Text style={s.queueTxt}>{queueCount} match{queueCount > 1 ? 's' : ''} en attente de sync</Text>
            <TouchableOpacity
              style={s.flushBtn}
              onPress={async () => {
                setSyncing(true);
                const { success, failed } = await flushSyncQueue();
                const q = await getSyncQueue();
                setQueueCount(q.length);
                setSyncResult(`🔄 File : ✅ ${success} resynchronisé${success > 1 ? 's' : ''}${failed > 0 ? `, ❌ ${failed} encore en attente` : ''}`);
                setSyncing(false);
              }}
              disabled={syncing || !loggedIn}
            >
              <Text style={s.flushBtnTxt}>Réessayer</Text>
            </TouchableOpacity>
          </View>
        )}
      </View>

      {/* Info Render */}
      <View style={s.card}>
        <View style={s.cardHeader}>
          <Ionicons name="information-circle-outline" size={14} color="#64748b" />
          <Text style={s.cardTitle}>DÉPLOIEMENT GRATUIT</Text>
        </View>
        <Text style={s.infoTxt}>
          Pour un serveur gratuit, déploie sur{' '}
          <Text style={{ color: ACCENT, fontWeight: '700' }}>Render.com</Text> en
          connectant ton dépôt GitHub. Le fichier{' '}
          <Text style={{ color: '#f1f5f9', fontFamily: 'monospace' }}>render.yaml</Text>{' '}
          est déjà configuré à la racine du projet.
        </Text>
      </View>

      <View style={{ height: 40 }} />
    </ScrollView>
  );
}

const s = StyleSheet.create({
  root: { flex: 1, backgroundColor: BG },
  content: { padding: 20, paddingTop: 50, gap: 16 },
  header: { gap: 4, marginBottom: 4 },
  title: { fontSize: 26, fontWeight: '900', color: '#f1f5f9' },
  subtitle: { fontSize: 13, color: '#475569' },
  card: {
    backgroundColor: CARD_BG, borderRadius: 18, padding: 16, gap: 12,
    borderWidth: 1, borderColor: '#1e2d45',
  },
  cardHeader: { flexDirection: 'row', alignItems: 'center', gap: 6, marginBottom: 2 },
  cardTitle: { fontSize: 11, fontWeight: '700', color: '#64748b', letterSpacing: 1 },
  input: {
    backgroundColor: '#0a0f1e', borderWidth: 1.5, borderColor: '#1e2d45',
    borderRadius: 12, paddingHorizontal: 14, paddingVertical: 12,
    color: '#f1f5f9', fontSize: 14,
  },
  testBtn: {
    flexDirection: 'row', alignItems: 'center', gap: 6, justifyContent: 'center',
    paddingVertical: 10, borderRadius: 10,
    borderWidth: 1.5, borderColor: ACCENT + '60', backgroundColor: ACCENT + '12',
  },
  testBtnTxt: { color: ACCENT, fontSize: 13, fontWeight: '700' },
  connBadge: { flexDirection: 'row', alignItems: 'center', gap: 6, padding: 10, borderRadius: 10 },
  connOk: { backgroundColor: '#4ade8015', borderWidth: 1, borderColor: '#4ade8030' },
  connFail: { backgroundColor: '#f8717115', borderWidth: 1, borderColor: '#f8717130' },
  connTxt: { fontSize: 13, fontWeight: '600' },
  connectedRow: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  connectedTxt: { fontSize: 15, fontWeight: '700', color: '#4ade80' },
  logoutBtn: {
    flexDirection: 'row', alignItems: 'center', gap: 6,
    paddingVertical: 8, paddingHorizontal: 12, borderRadius: 8,
    backgroundColor: '#1e2d45', alignSelf: 'flex-start',
  },
  logoutTxt: { fontSize: 12, color: '#94a3b8', fontWeight: '600' },
  authRow: { flexDirection: 'row', gap: 10 },
  authBtn: { flex: 1, paddingVertical: 12, borderRadius: 12, alignItems: 'center' },
  authBtnSecondary: { borderWidth: 1.5, borderColor: ACCENT, backgroundColor: ACCENT + '15' },
  authBtnTxt: { fontSize: 13, fontWeight: '800', color: '#fff' },
  lastSyncRow: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  lastSyncTxt: { fontSize: 12, color: '#64748b', fontStyle: 'italic' },
  syncResultRow: { backgroundColor: '#1e2d45', borderRadius: 10, padding: 10 },
  syncResultTxt: { fontSize: 13, color: '#f1f5f9', fontWeight: '600' },
  syncBtn: {
    flexDirection: 'row', alignItems: 'center', gap: 8, justifyContent: 'center',
    backgroundColor: ACCENT, paddingVertical: 14, borderRadius: 14,
  },
  syncBtnTxt: { color: '#fff', fontSize: 14, fontWeight: '800' },
  syncHint: { fontSize: 11, color: '#475569', fontStyle: 'italic' },
  queueRow: {
    flexDirection: 'row', alignItems: 'center', gap: 6, flexWrap: 'wrap',
    backgroundColor: '#f59e0b18', borderRadius: 10, padding: 10, borderWidth: 1, borderColor: '#f59e0b30',
  },
  queueTxt: { fontSize: 12, color: '#f59e0b', fontWeight: '700', flex: 1 },
  flushBtn: { paddingHorizontal: 10, paddingVertical: 4, backgroundColor: '#f59e0b30', borderRadius: 8 },
  flushBtnTxt: { fontSize: 11, color: '#f59e0b', fontWeight: '800' },
  infoTxt: { fontSize: 12, color: '#64748b', lineHeight: 18 },
});
