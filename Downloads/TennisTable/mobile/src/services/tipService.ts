import { MatchRecord, PlayerProfile } from '../types';

export interface Tip {
  id: string;
  emoji: string;
  title: string;
  body: string;
  priority: number; // higher = more relevant
}

function pct(n: number, total: number) {
  return total > 0 ? Math.round((n / total) * 100) : 0;
}

export function generateTips(matches: MatchRecord[], profile: PlayerProfile | null): Tip[] {
  const tips: Tip[] = [];
  if (!profile || matches.length === 0) {
    tips.push({
      id: 'start',
      emoji: '🏓',
      title: 'Commences à jouer !',
      body: 'Joue au moins 5 matchs pour recevoir des conseils personnalisés.',
      priority: 1,
    });
    return tips;
  }

  const profileMatches = matches.filter(
    m => m.profile1Id === profile.id || m.profile2Id === profile.id
  );
  if (profileMatches.length === 0) {
    tips.push({
      id: 'no_profile',
      emoji: '👤',
      title: 'Lie ton profil à un match',
      body: 'Sélectionne ton profil dans l\'écran Jouer pour recevoir des conseils.',
      priority: 1,
    });
    return tips;
  }

  const winRate = pct(profile.wins, profile.wins + profile.losses);
  const total = profileMatches.length;

  // Win rate advice
  if (winRate < 40 && total >= 5) {
    tips.push({
      id: 'low_winrate',
      emoji: '📉',
      title: 'Taux de victoire faible',
      body: `Tu gagnes ${winRate}% de tes matchs. Concentre-toi sur les drills FH Drive pour solidifier ta base.`,
      priority: 5,
    });
  } else if (winRate >= 70) {
    tips.push({
      id: 'high_winrate',
      emoji: '🔥',
      title: 'Excellent niveau !',
      body: `${winRate}% de victoires — tu domines tes adversaires. Tente des tournois pour te challenger.`,
      priority: 3,
    });
  }

  // Stroke analysis
  const totalStrokes1 = profileMatches.reduce((acc, m) => {
    if (m.profile1Id === profile.id) {
      return acc + Object.values(m.strokes1).reduce((a, b) => a + b, 0);
    }
    return acc + Object.values(m.strokes2).reduce((a, b) => a + b, 0);
  }, 0);

  const bhDrive = profileMatches.reduce((acc, m) => {
    if (m.profile1Id === profile.id) return acc + m.strokes1.bhDrive;
    return acc + m.strokes2.bhDrive;
  }, 0);
  const fhDrive = profileMatches.reduce((acc, m) => {
    if (m.profile1Id === profile.id) return acc + m.strokes1.fhDrive;
    return acc + m.strokes2.fhDrive;
  }, 0);
  const fhSmash = profileMatches.reduce((acc, m) => {
    if (m.profile1Id === profile.id) return acc + m.strokes1.fhSmash;
    return acc + m.strokes2.fhSmash;
  }, 0);
  const fhLoop = profileMatches.reduce((acc, m) => {
    if (m.profile1Id === profile.id) return acc + m.strokes1.fhLoop;
    return acc + m.strokes2.fhLoop;
  }, 0);

  const bhPct = pct(bhDrive, totalStrokes1);
  const fhDrivePct = pct(fhDrive, totalStrokes1);
  const smashPct = pct(fhSmash, totalStrokes1);
  const loopPct = pct(fhLoop, totalStrokes1);

  // FH/BH imbalance
  if (fhDrivePct > 0 && bhPct < 10 && totalStrokes1 > 20) {
    tips.push({
      id: 'low_bh',
      emoji: '🏓',
      title: 'Revers peu utilisé',
      body: `Seulement ${bhPct}% de revers. Entraîne ton BH Drive pour être moins prévisible en match.`,
      priority: 4,
    });
  }
  if (bhPct > 0 && fhDrivePct < 15 && totalStrokes1 > 20) {
    tips.push({
      id: 'low_fh',
      emoji: '💪',
      title: 'FH Drive à développer',
      body: `Ton coup droit (${fhDrivePct}%) est sous-utilisé. C'est l'arme offensive principale — pratique-le en drill.`,
      priority: 4,
    });
  }

  // Too much smash
  if (smashPct > 40) {
    tips.push({
      id: 'too_smash',
      emoji: '⚡',
      title: 'Trop de smash',
      body: `${smashPct}% de smash, c'est risqué. Alterne avec des loops pour plus de régularité.`,
      priority: 4,
    });
  }

  // Smash > 60%: diversification
  if (smashPct > 60) {
    tips.push({
      id: 'smash_overuse',
      emoji: '🎯',
      title: 'Diversifie ton jeu',
      body: `Plus de 60% de smash indique un jeu trop direct. Travaille le placement et le loop pour gagner en points.`,
      priority: 5,
    });
  }

  if (loopPct < 10 && totalStrokes1 > 30) {
    tips.push({
      id: 'low_loop',
      emoji: '🌀',
      title: 'Développe ton FH Loop',
      body: `Le topspin FH est l'arme n°1 au ping-pong. Pratique-le en drill pour varier tes attaques.`,
      priority: 3,
    });
  }

  // Streak advice
  if (profile.currentStreak >= 3) {
    tips.push({
      id: 'on_fire',
      emoji: '🔥',
      title: `Série de ${profile.currentStreak} !`,
      body: 'Tu es en forme ! C\'est le bon moment pour défier un adversaire plus fort.',
      priority: 2,
    });
  } else if (profile.currentStreak <= -3) {
    tips.push({
      id: 'losing_streak',
      emoji: '❄️',
      title: 'Série de défaites',
      body: 'Fais une session de drill avant ton prochain match pour retrouver la confiance.',
      priority: 5,
    });
  }

  // Mental: long losing streak > 5
  if (profile.currentStreak <= -5) {
    tips.push({
      id: 'mental_reset',
      emoji: '🧘',
      title: 'Pause & reset mental',
      body: `Plus de 5 défaites d'affilée : prends une pause de 48h puis reviens avec un objectif simple (juste s'amuser).`,
      priority: 6,
    });
  }

  // Win rate drop last 5 matches
  const last5 = profileMatches.slice(0, 5);
  if (last5.length >= 5) {
    const recentWins = last5.filter(m => {
      const isP1 = m.profile1Id === profile.id;
      return isP1 ? m.winner === 0 : m.winner === 1;
    }).length;
    if (recentWins <= 1 && winRate > 40) {
      tips.push({
        id: 'recent_decline',
        emoji: '📊',
        title: 'Baisse récente de forme',
        body: `Seulement ${recentWins}/5 victoires récentes alors que tu es habituellement à ${winRate}%. Probable fatigue — repose-toi.`,
        priority: 5,
      });
    }
  }

  // Short matches: abandon / forfeits
  const avgDuration = profileMatches.reduce((acc, m) => acc + m.durationSecs, 0) / total;
  if (avgDuration < 120 && total >= 3) {
    tips.push({
      id: 'short_matches',
      emoji: '⏱',
      title: 'Matchs très courts',
      body: `Durée moyenne ${Math.round(avgDuration)}s — possibles abandons ou matchs non terminés. Joue en 21 pts pour travailler la constance.`,
      priority: 2,
    });
  }

  // Late-game losses (close score defeats)
  const closeDefeats = profileMatches.filter(m => {
    const isP1 = m.profile1Id === profile.id;
    const iLost = isP1 ? m.winner === 1 : m.winner === 0;
    if (!iLost) return false;
    const myScore = isP1 ? m.score1 : m.score2;
    const oppScore = isP1 ? m.score2 : m.score1;
    const pts = m.config?.pointsToWin ?? 11;
    return oppScore >= pts - 2 && Math.abs(myScore - oppScore) <= 2;
  }).length;
  if (closeDefeats >= 2 && total >= 5) {
    tips.push({
      id: 'late_game_loss',
      emoji: '🎯',
      title: 'Défaites en fin de set',
      body: `${closeDefeats} défaites en situation serrée. Travaille la gestion du stress : respire profondément entre les points décisifs.`,
      priority: 4,
    });
  }

  // ELO stagnant 10+ matches
  if (total >= 10) {
    const eloChanges = profileMatches.slice(0, 10).map(m =>
      Math.abs(m.profile1Id === profile.id ? (m.eloChange1 ?? 0) : (m.eloChange2 ?? 0))
    );
    const avgEloChange = eloChanges.reduce((a, b) => a + b, 0) / eloChanges.length;
    if (avgEloChange < 5) {
      tips.push({
        id: 'elo_stagnant',
        emoji: '📈',
        title: 'ELO stagnant',
        body: `Peu de variation ELO sur tes 10 derniers matchs. Cherche des adversaires de niveau différent pour progresser.`,
        priority: 3,
      });
    }
  }

  // Never used a racket
  const hasRacketData = profileMatches.some(m => m.note?.includes('raquette') || m.note?.includes('Raquette'));
  if (total >= 3 && !hasRacketData && profile.wins + profile.losses >= 5) {
    tips.push({
      id: 'no_racket',
      emoji: '🏏',
      title: 'Utilise la raquette BLE',
      body: 'Connecte ta raquette intelligente via BLE pour une analyse automatique de tes coups en temps réel.',
      priority: 2,
    });
  }

  // ELO trend advice
  if (profile.elo < 1000) {
    tips.push({
      id: 'low_elo',
      emoji: '📈',
      title: 'Progresser rapidement',
      body: 'À ce niveau, concentre-toi sur la régularité plutôt que la puissance. 20 drills FH Drive par jour.',
      priority: 3,
    });
  } else if (profile.elo > 1600) {
    tips.push({
      id: 'high_elo',
      emoji: '🏆',
      title: 'Niveau expert',
      body: 'Travaille le placement de balle et la lecture du jeu adverse pour progresser encore.',
      priority: 2,
    });
  }

  return tips.sort((a, b) => b.priority - a.priority).slice(0, 6);
}

// Fatigue detection: if last 3 matches of a session show declining score ratio
export function detectFatigue(matches: MatchRecord[], profileId: string): boolean {
  const recent = matches
    .filter(m => m.profile1Id === profileId || m.profile2Id === profileId)
    .slice(0, 6);
  if (recent.length < 4) return false;

  const scores = recent.map(m => {
    const isP1 = m.profile1Id === profileId;
    const myScore = isP1 ? m.score1 : m.score2;
    const oppScore = isP1 ? m.score2 : m.score1;
    return myScore - oppScore; // positive = winning
  });

  // Decreasing trend in last 4 matches
  let decreasing = 0;
  for (let i = 1; i < scores.length; i++) {
    if (scores[i] < scores[i - 1]) decreasing++;
  }
  return decreasing >= 3;
}
