import React, { useEffect, useState } from 'react';
import { TouchableOpacity, StyleSheet, Animated, View, ActivityIndicator } from 'react-native';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import { Ionicons } from '@expo/vector-icons';
import OnboardingScreen, { isOnboardingDone } from '../screens/OnboardingScreen';
import DashboardScreen        from '../screens/DashboardScreen';
import PlayScreen             from '../screens/PlayScreen';
import HistoryScreen          from '../screens/HistoryScreen';
import StatsScreen            from '../screens/StatsScreen';
import ProfilesScreen         from '../screens/ProfilesScreen';
import MoreScreen             from '../screens/MoreScreen';
import TournamentScreen       from '../screens/TournamentScreen';
import TrainingHistoryScreen  from '../screens/TrainingHistoryScreen';
import SettingsScreen         from '../screens/SettingsScreen';
import EloChartScreen         from '../screens/EloChartScreen';
import ClubScreen             from '../screens/ClubScreen';
import ChampionsScreen        from '../screens/ChampionsScreen';
import RefereeScreen          from '../screens/RefereeScreen';
import CloudSyncScreen        from '../screens/CloudSyncScreen';
import { ACCENT, CARD_BG } from '../types';

export type TabParams = {
  Dashboard:  undefined;
  Play:       undefined;
  History:    undefined;
  Stats:      undefined;
  Profiles:   undefined;
  More:       undefined;
  // Hidden (navigable via MoreScreen)
  Referee:    undefined;
  Tournament: undefined;
  Training:   undefined;
  EloChart:   undefined;
  Club:       undefined;
  Champions:  undefined;
  Settings:   undefined;
  CloudSync:  undefined;
};

export type RootStackParams = {
  Tabs: undefined;
  TrainingHistory: undefined;
};

const Tab   = createBottomTabNavigator<TabParams>();
const Stack = createNativeStackNavigator<RootStackParams>();

// Animated spring tab button
function TabButton({ children, onPress, accessibilityState }: any) {
  const scale  = React.useRef(new Animated.Value(1)).current;
  const active = accessibilityState?.selected as boolean;

  const handlePress = () => {
    Animated.sequence([
      Animated.spring(scale, { toValue: 0.82, useNativeDriver: true, speed: 40, bounciness: 0 }),
      Animated.spring(scale, { toValue: 1,    useNativeDriver: true, speed: 20, bounciness: 12 }),
    ]).start();
    onPress?.();
  };

  return (
    <TouchableOpacity style={s.tabBtn} onPress={handlePress} activeOpacity={1}>
      <Animated.View style={[s.tabInner, active && s.tabInnerActive, { transform: [{ scale }] }]}>
        {children}
      </Animated.View>
    </TouchableOpacity>
  );
}

const MAIN_TABS: { name: keyof TabParams; label: string; icon: keyof typeof Ionicons.glyphMap; iconFilled: keyof typeof Ionicons.glyphMap }[] = [
  { name: 'Dashboard', label: 'Accueil',    icon: 'home-outline',        iconFilled: 'home' },
  { name: 'Play',      label: 'Jouer',      icon: 'play-circle-outline', iconFilled: 'play-circle' },
  { name: 'History',   label: 'Historique', icon: 'time-outline',        iconFilled: 'time' },
  { name: 'Stats',     label: 'Stats',      icon: 'bar-chart-outline',   iconFilled: 'bar-chart' },
  { name: 'Profiles',  label: 'Profils',    icon: 'person-outline',      iconFilled: 'person' },
  { name: 'More',      label: 'Plus',       icon: 'grid-outline',        iconFilled: 'grid' },
];

const SCREEN_MAP: Record<string, React.ComponentType<any>> = {
  Dashboard: DashboardScreen,
  Play:      PlayScreen,
  History:   HistoryScreen,
  Stats:     StatsScreen,
  Profiles:  ProfilesScreen,
  More:      MoreScreen,
  Referee:   RefereeScreen,
  Tournament:TournamentScreen,
  Training:  TrainingHistoryScreen,
  EloChart:  EloChartScreen,
  Club:      ClubScreen,
  Champions: ChampionsScreen,
  Settings:  SettingsScreen,
  CloudSync: CloudSyncScreen,
};

const HIDDEN: Array<keyof TabParams> = ['Referee', 'Tournament', 'Training', 'EloChart', 'Club', 'Champions', 'Settings', 'CloudSync'];

function Tabs() {
  return (
    <Tab.Navigator
      screenOptions={({ route }) => {
        const isVisible = MAIN_TABS.some(t => t.name === route.name);
        return {
          headerShown: false,
          tabBarStyle: isVisible ? s.tabBar : { display: 'none' },
          tabBarActiveTintColor:   ACCENT,
          tabBarInactiveTintColor: '#475569',
          tabBarLabelStyle: s.tabLabel,
          tabBarButton: isVisible ? (props) => <TabButton {...props} /> : () => null,
        };
      }}
    >
      {MAIN_TABS.map(t => (
        <Tab.Screen
          key={t.name}
          name={t.name}
          component={SCREEN_MAP[t.name]}
          options={{
            tabBarLabel: t.label,
            tabBarIcon: ({ color, focused }) => (
              <Ionicons name={focused ? t.iconFilled : t.icon} size={22} color={color} />
            ),
          }}
        />
      ))}
      {HIDDEN.map(name => (
        <Tab.Screen key={name} name={name} component={SCREEN_MAP[name]} />
      ))}
    </Tab.Navigator>
  );
}

export default function AppNavigator() {
  const [ready, setReady]           = useState(false);
  const [showOnboard, setShowOnboard] = useState(false);

  useEffect(() => {
    isOnboardingDone().then(done => {
      setShowOnboard(!done);
      setReady(true);
    });
  }, []);

  if (!ready) {
    return (
      <View style={{ flex: 1, backgroundColor: '#0a0f1e', alignItems: 'center', justifyContent: 'center' }}>
        <ActivityIndicator color="#6366f1" size="large" />
      </View>
    );
  }

  if (showOnboard) {
    return <OnboardingScreen onDone={() => setShowOnboard(false)} />;
  }

  return (
    <Stack.Navigator screenOptions={{ headerShown: false }}>
      <Stack.Screen name="Tabs" component={Tabs} />
    </Stack.Navigator>
  );
}

const s = StyleSheet.create({
  tabBar: {
    backgroundColor: CARD_BG,
    borderTopColor: '#1e2d45',
    borderTopWidth: 1,
    height: 72,
    paddingBottom: 10,
    paddingTop: 4,
    paddingHorizontal: 4,
  },
  tabLabel: { fontSize: 10, fontWeight: '700', letterSpacing: 0.2, marginTop: 2 },
  tabBtn:   { flex: 1, alignItems: 'center', justifyContent: 'center' },
  tabInner: {
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 6,
    paddingHorizontal: 10,
    borderRadius: 14,
    gap: 2,
  },
  tabInnerActive: { backgroundColor: ACCENT + '1a' },
});
