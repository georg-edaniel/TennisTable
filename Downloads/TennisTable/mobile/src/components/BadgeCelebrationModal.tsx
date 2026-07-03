import React, { useEffect, useRef, useState } from 'react';
import { Animated, Modal, StyleSheet, Text, TouchableOpacity, View } from 'react-native';
import Confetti from './Confetti';
import { BadgeDef } from '../services/badgeService';

interface Props {
  badges: BadgeDef[];
  onClose: () => void;
}

export default function BadgeCelebrationModal({ badges, onClose }: Props) {
  const [index, setIndex] = useState(0);
  const scale = useRef(new Animated.Value(0)).current;
  const opacity = useRef(new Animated.Value(0)).current;

  const current = badges[index];

  useEffect(() => {
    if (!current) return;
    scale.setValue(0);
    opacity.setValue(0);
    Animated.parallel([
      Animated.spring(scale, {
        toValue: 1, useNativeDriver: true,
        speed: 10, bounciness: 14,
      }),
      Animated.timing(opacity, {
        toValue: 1, duration: 250, useNativeDriver: true,
      }),
    ]).start();
  }, [index]);

  if (!current) return null;

  function handleNext() {
    if (index + 1 < badges.length) {
      scale.setValue(0);
      setIndex(i => i + 1);
    } else {
      onClose();
    }
  }

  return (
    <Modal visible transparent animationType="fade">
      <Confetti active />
      <Animated.View style={[s.overlay, { opacity }]}>
        <Animated.View style={[s.card, { transform: [{ scale }] }]}>
          <Text style={s.unlocked}>🎉 Badge débloqué !</Text>
          <Text style={s.emoji}>{current.emoji}</Text>
          <Text style={s.name}>{current.name}</Text>
          <Text style={s.desc}>{current.description}</Text>
          <Text style={s.category}>{current.category}</Text>
          {badges.length > 1 && (
            <Text style={s.counter}>{index + 1} / {badges.length}</Text>
          )}
          <TouchableOpacity style={s.btn} onPress={handleNext}>
            <Text style={s.btnTxt}>
              {index + 1 < badges.length ? 'Suivant →' : 'Super !'}
            </Text>
          </TouchableOpacity>
        </Animated.View>
      </Animated.View>
    </Modal>
  );
}

const s = StyleSheet.create({
  overlay: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.85)',
    alignItems: 'center',
    justifyContent: 'center',
    padding: 32,
  },
  card: {
    backgroundColor: '#131929',
    borderRadius: 28,
    padding: 32,
    alignItems: 'center',
    gap: 12,
    borderWidth: 2,
    borderColor: '#f59e0b60',
    width: '100%',
  },
  unlocked: { fontSize: 13, color: '#f59e0b', fontWeight: '800', letterSpacing: 1 },
  emoji: { fontSize: 72, lineHeight: 84 },
  name: { fontSize: 24, fontWeight: '900', color: '#f1f5f9', textAlign: 'center' },
  desc: { fontSize: 14, color: '#94a3b8', textAlign: 'center', lineHeight: 20 },
  category: {
    fontSize: 11, color: '#f59e0b', fontWeight: '700',
    backgroundColor: '#f59e0b20', paddingHorizontal: 10, paddingVertical: 4,
    borderRadius: 8, overflow: 'hidden',
  },
  counter: { fontSize: 11, color: '#475569' },
  btn: {
    marginTop: 8,
    backgroundColor: '#6366f1',
    paddingHorizontal: 36,
    paddingVertical: 14,
    borderRadius: 16,
  },
  btnTxt: { color: '#fff', fontSize: 15, fontWeight: '800' },
});
