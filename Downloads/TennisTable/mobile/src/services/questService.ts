import { MatchRecord, TrainingSession } from '../types';

export interface QuestDef {
  id: string;
  emoji: string;
  title: string;
  titleEn: string;
  description: string;
  descriptionEn: string;
  xp: number;
  check: (matches: MatchRecord[], trainings: TrainingSession[]) => boolean;
}

// Quests rotate based on day of week (0=Sun...6=Sat), 3 quests per day
export const ALL_QUESTS: QuestDef[] = [
  {
    id: 'win_1', emoji: '🏆', title: 'Première victoire', titleEn: 'First win',
    description: 'Gagne 1 match aujourd\'hui', descriptionEn: 'Win 1 match today', xp: 50,
    check: (m) => m.filter(x => isToday(x.date)).some(x => x.winner === 0 || x.winner === 1),
  },
  {
    id: 'win_3', emoji: '🔥', title: 'Triple victoire', titleEn: 'Triple win',
    description: 'Gagne 3 matchs aujourd\'hui', descriptionEn: 'Win 3 matches today', xp: 150,
    check: (m) => m.filter(x => isToday(x.date) && (x.winner === 0 || x.winner === 1)).length >= 3,
  },
  {
    id: 'play_5', emoji: '🏓', title: 'Match après match', titleEn: 'Match after match',
    description: 'Joue 5 matchs aujourd\'hui', descriptionEn: 'Play 5 matches today', xp: 100,
    check: (m) => m.filter(x => isToday(x.date)).length >= 5,
  },
  {
    id: 'train_50', emoji: '🎯', title: 'Séance intensive', titleEn: 'Intensive session',
    description: 'Complète 50 frappes en entraînement', descriptionEn: 'Complete 50 strokes in training', xp: 80,
    check: (_m, t) => t.filter(x => isToday(x.date)).reduce((acc, s) => acc + s.completed, 0) >= 50,
  },
  {
    id: 'fh_smash_10', emoji: '💥', title: 'Smasheur', titleEn: 'Smasher',
    description: 'Fais 10 FH Smash en match', descriptionEn: 'Hit 10 FH Smash in matches', xp: 70,
    check: (m) => m.filter(x => isToday(x.date)).reduce((acc, x) => acc + x.strokes1.fhSmash + x.strokes2.fhSmash, 0) >= 10,
  },
  {
    id: 'long_match', emoji: '⏱', title: 'Marathon', titleEn: 'Marathon',
    description: 'Joue un match de plus de 10 minutes', descriptionEn: 'Play a match over 10 minutes', xp: 90,
    check: (m) => m.filter(x => isToday(x.date)).some(x => x.durationSecs >= 600),
  },
  {
    id: 'win_bo3', emoji: '🥇', title: 'Champion best-of-3', titleEn: 'Best-of-3 champ',
    description: 'Gagne un match en Best-of-3', descriptionEn: 'Win a best-of-3 match', xp: 120,
    check: (m) => m.filter(x => isToday(x.date)).some(x => (x.config?.numSets ?? 1) >= 3),
  },
  {
    id: 'high_score', emoji: '🎖', title: 'Score élevé', titleEn: 'High score',
    description: 'Gagne un match avec au moins 15 points', descriptionEn: 'Win a match with at least 15 points', xp: 60,
    check: (m) => m.filter(x => isToday(x.date)).some(x => Math.max(x.score1, x.score2) >= 15),
  },
  {
    id: 'bh_drive_15', emoji: '🏓', title: 'Revers dominant', titleEn: 'Dominant backhand',
    description: 'Fais 15 BH Drive en match', descriptionEn: 'Hit 15 BH Drive in matches', xp: 75,
    check: (m) => m.filter(x => isToday(x.date)).reduce((acc, x) => acc + x.strokes1.bhDrive + x.strokes2.bhDrive, 0) >= 15,
  },
  {
    id: 'train_today', emoji: '💪', title: 'Entraînement du jour', titleEn: 'Train today',
    description: 'Complète une séance d\'entraînement', descriptionEn: 'Complete a training session', xp: 50,
    check: (_m, t) => t.some(x => isToday(x.date)),
  },
  {
    id: 'close_win', emoji: '😤', title: 'Victoire serrée', titleEn: 'Close win',
    description: 'Gagne un match en déuce', descriptionEn: 'Win a match in deuce', xp: 100,
    check: (m) => m.filter(x => isToday(x.date)).some(x => {
      const diff = Math.abs(x.score1 - x.score2);
      return diff <= 2 && Math.max(x.score1, x.score2) >= 11;
    }),
  },
  {
    id: 'perfect_21', emoji: '🎯', title: 'Perfection 21', titleEn: 'Perfect 21',
    description: 'Joue un match à 21 points', descriptionEn: 'Play a 21-point match', xp: 80,
    check: (m) => m.filter(x => isToday(x.date)).some(x => x.config?.pointsToWin === 21),
  },
  {
    id: 'fh_loop_10', emoji: '🌀', title: 'Loopeur fou', titleEn: 'Loop master',
    description: 'Fais 10 FH Loop en match', descriptionEn: 'Hit 10 FH Loop in matches', xp: 70,
    check: (m) => m.filter(x => isToday(x.date)).reduce((acc, x) => acc + x.strokes1.fhLoop + x.strokes2.fhLoop, 0) >= 10,
  },
  {
    id: 'comeback', emoji: '🔄', title: 'Come-back', titleEn: 'Comeback',
    description: 'Joue un match où le score a changé de tête', descriptionEn: 'Play a match where the lead changed', xp: 110,
    check: (m) => m.filter(x => isToday(x.date)).some(x => x.sets && x.sets.length > 1),
  },
  {
    id: 'fh_drive_20', emoji: '💪', title: 'FH Drive ×20', titleEn: 'FH Drive ×20',
    description: 'Fais 20 FH Drive en un seul match', descriptionEn: 'Hit 20 FH Drive in one match', xp: 80,
    check: (m) => m.filter(x => isToday(x.date)).some(x => x.strokes1.fhDrive + x.strokes2.fhDrive >= 20),
  },
  {
    id: 'train_loop', emoji: '🌀', title: 'Session loop', titleEn: 'Loop session',
    description: 'Complète 30 FH Loop en entraînement', descriptionEn: 'Complete 30 FH Loop in training', xp: 90,
    check: (_m, t) => t.filter(x => isToday(x.date) && x.stroke === 'FH Loop').reduce((acc, s) => acc + s.completed, 0) >= 30,
  },
  {
    id: 'win_bo5', emoji: '🥇', title: 'Champion best-of-5', titleEn: 'Best-of-5 champ',
    description: 'Gagne un match Best-of-5', descriptionEn: 'Win a best-of-5 match', xp: 200,
    check: (m) => m.filter(x => isToday(x.date)).some(x => (x.config?.numSets ?? 1) >= 5 && (x.winner === 0 || x.winner === 1)),
  },
  {
    id: 'two_profiles', emoji: '👥', title: 'Deux profils', titleEn: 'Two profiles',
    description: 'Joue avec 2 profils différents aujourd\'hui', descriptionEn: 'Play with 2 different profiles today', xp: 70,
    check: (m) => {
      const todayMatches = m.filter(x => isToday(x.date));
      const ids = new Set<string>();
      todayMatches.forEach(x => { if (x.profile1Id) ids.add(x.profile1Id); if (x.profile2Id) ids.add(x.profile2Id); });
      return ids.size >= 2;
    },
  },
  {
    id: 'crushing_win', emoji: '💣', title: 'Victoire écrasante', titleEn: 'Crushing win',
    description: 'Gagne un match avec 5+ points d\'écart', descriptionEn: 'Win by 5+ point margin', xp: 85,
    check: (m) => m.filter(x => isToday(x.date)).some(x => {
      const won = x.winner === 0 || x.winner === 1;
      return won && Math.abs(x.score1 - x.score2) >= 5;
    }),
  },
];

function isToday(dateStr: string): boolean {
  return new Date(dateStr).toDateString() === new Date().toDateString();
}

/** Returns 3 quests for today (rotate by day of week) */
export function getTodayQuests(): QuestDef[] {
  const day = new Date().getDay();
  const start = (day * 3) % ALL_QUESTS.length;
  const result: QuestDef[] = [];
  for (let i = 0; i < 3; i++) {
    result.push(ALL_QUESTS[(start + i) % ALL_QUESTS.length]);
  }
  return result;
}

/** Check how many of today's quests are completed */
export function checkQuests(
  quests: QuestDef[],
  matches: MatchRecord[],
  trainings: TrainingSession[]
): { quest: QuestDef; done: boolean }[] {
  return quests.map(q => ({ quest: q, done: q.check(matches, trainings) }));
}
