import * as Speech from 'expo-speech';
import * as Haptics from 'expo-haptics';

export type VictorySound = 'fanfare' | 'crowd' | 'bell' | 'none';

const SPEECH_MAP: Record<VictorySound, string | null> = {
  fanfare: 'Victoire ! Bravo champion !',
  crowd: 'Magnifique partie !',
  bell: 'Match terminé.',
  none: null,
};

export async function playVictorySound(type: VictorySound): Promise<void> {
  if (type === 'none') return;
  const text = SPEECH_MAP[type];
  if (!text) return;
  try {
    Speech.stop();
    await new Promise<void>(res => setTimeout(res, 200));
    Speech.speak(text, { language: 'fr-FR', pitch: 1.1, rate: 0.9 });
    await Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success).catch(() => {});
  } catch {
    // Speech not available, ignore
  }
}

export async function playPointSound(): Promise<void> {
  try {
    await Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
  } catch {
    // ignore
  }
}

export async function unloadSound(): Promise<void> {
  try { Speech.stop(); } catch { }
}
