import React from 'react';
import { View, Text, TouchableOpacity, ScrollView, StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useNavigation } from '@react-navigation/native';
import { BottomTabNavigationProp } from '@react-navigation/bottom-tabs';
import { LinearGradient } from 'expo-linear-gradient';
import { TabParams } from '../navigation/AppNavigator';
import { BG, CARD_BG, ACCENT } from '../types';

type Nav = BottomTabNavigationProp<TabParams>;

const ITEMS: {
  name: keyof TabParams;
  label: string;
  icon: keyof typeof Ionicons.glyphMap;
  color: string;
  gradient: [string, string];
}[] = [
  { name: 'Tournament',    label: 'Tournoi',   icon: 'trophy',        color: '#f59e0b', gradient: ['#f59e0b22', '#f59e0b06'] },
  { name: 'EloChart',     label: 'ELO',        icon: 'trending-up',   color: '#22c55e', gradient: ['#22c55e22', '#22c55e06'] },
  { name: 'Champions',    label: 'Palmarès',   icon: 'medal',         color: '#a855f7', gradient: ['#a855f722', '#a855f706'] },
  { name: 'Club',         label: 'Club',       icon: 'people',        color: '#3b82f6', gradient: ['#3b82f622', '#3b82f606'] },
  { name: 'Referee',      label: 'Arbitre',    icon: 'flag',          color: '#f43f5e', gradient: ['#f43f5e22', '#f43f5e06'] },
  { name: 'Training',     label: 'Drills',     icon: 'fitness',       color: '#10b981', gradient: ['#10b98122', '#10b98106'] },
  { name: 'Settings',     label: 'Réglages',   icon: 'settings-sharp',color: '#64748b', gradient: ['#64748b22', '#64748b06'] },
  { name: 'CloudSync',    label: 'Cloud Sync', icon: 'cloud-upload',  color: '#0ea5e9', gradient: ['#0ea5e922', '#0ea5e906'] },
];

export default function MoreScreen() {
  const nav = useNavigation<Nav>();

  return (
    <ScrollView style={s.root} contentContainerStyle={s.content} showsVerticalScrollIndicator={false}>
      <Text style={s.title}>Plus</Text>
      <View style={s.grid}>
        {ITEMS.map(item => (
          <TouchableOpacity
            key={item.name}
            style={s.cardWrap}
            activeOpacity={0.75}
            onPress={() => nav.navigate(item.name)}
          >
            <LinearGradient
              colors={item.gradient}
              start={{ x: 0, y: 0 }}
              end={{ x: 1, y: 1 }}
              style={s.card}
            >
              <View style={[s.iconCircle, { backgroundColor: item.color + '25' }]}>
                <Ionicons name={item.icon} size={26} color={item.color} />
              </View>
              <Text style={s.label}>{item.label}</Text>
            </LinearGradient>
          </TouchableOpacity>
        ))}
      </View>
    </ScrollView>
  );
}

const s = StyleSheet.create({
  root: { flex: 1, backgroundColor: BG },
  content: { padding: 20, paddingTop: 60 },
  title: { fontSize: 28, fontWeight: '900', color: '#f1f5f9', marginBottom: 24 },
  grid: { flexDirection: 'row', flexWrap: 'wrap', gap: 14 },
  cardWrap: { width: '47%' },
  card: {
    borderRadius: 18,
    padding: 20,
    alignItems: 'center',
    gap: 12,
    borderWidth: 1,
    borderColor: '#1e2d45',
    backgroundColor: CARD_BG,
  },
  iconCircle: {
    width: 54,
    height: 54,
    borderRadius: 27,
    alignItems: 'center',
    justifyContent: 'center',
  },
  label: { fontSize: 13, fontWeight: '700', color: '#f1f5f9', textAlign: 'center' },
});
