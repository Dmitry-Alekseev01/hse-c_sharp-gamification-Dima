import React, { useState, useMemo } from 'react';
import { Link } from 'react-router-dom';
import {
  useUserProfile,
  useUserProgress,
  useTests,
  useMaterials,
  useLevels,
} from '../../hooks/useHomeData';
import { useQueries } from '@tanstack/react-query';
import { fetchUserAnswers } from '../../api/api';
import './HomePage.css';

const Home = () => {
  const [activeTab, setActiveTab] = useState('roadmap');
  const [activeFilter, setActiveFilter] = useState('all');

  const { data: profile, isLoading: profileLoading } = useUserProfile();
  const { data: progress, isLoading: progressLoading } = useUserProgress(profile?.id);
  const { data: tests, isLoading: testsLoading } = useTests();
  const { data: materials, isLoading: materialsLoading } = useMaterials();
  const { data: levels, isLoading: levelsLoading } = useLevels();

  const answersQueries = useQueries({
    queries: (tests || []).map((test) => ({
      queryKey: ['userAnswers', test.id],
      queryFn: () => fetchUserAnswers(test.id),
    })),
  });

  const { stats, deadlines, badges, currentLevel } = useMemo(() => {
    if (!tests || !answersQueries.length)
      return { stats: {}, deadlines: [], badges: [], currentLevel: null };
    let completedTests = 0;
    let totalScoreSum = 0;
    let testsWithScore = 0;
    const deadlinesList = [];
    answersQueries.forEach((res, idx) => {
      const answers = res.data;
      const test = tests[idx];
      if (test.deadline) {
        const daysLeft = Math.ceil((new Date(test.deadline) - new Date()) / (1000 * 60 * 60 * 24));
        deadlinesList.push({
          id: test.id,
          title: test.title,
          type: 'test',
          deadline: test.deadline,
          daysLeft,
          priority: daysLeft <= 3 ? 'high' : daysLeft <= 7 ? 'medium' : 'low',
        });
      }
      if (answers?.length) {
        completedTests++;
        const userScore = answers.reduce((sum, ans) => sum + (ans.score || 0), 0);
        if (test.max_score) {
          const percentage = (userScore / test.max_score) * 100;
          totalScoreSum += percentage;
          testsWithScore++;
        }
      }
    });
    const averageScore = testsWithScore ? Math.round(totalScoreSum / testsWithScore) : 0;
    const totalPoints = progress?.total_points || 0;
    const streakDays = progress?.streak_days || 0;
    const badgesList = progress?.badges || [];
    const current = progress?.current_level;
    return {
      stats: {
        totalTests: tests.length,
        completedTests,
        averageScore,
        totalPoints,
        streakDays,
        totalMaterials: materials?.length || 0,
      },
      deadlines: deadlinesList,
      badges: badgesList,
      currentLevel: current,
    };
  }, [tests, answersQueries, progress, materials]);

  if (profileLoading || progressLoading || testsLoading || materialsLoading || levelsLoading) {
    return <div className="loading">Загрузка...</div>;
  }

  const getAverageScoreIn10Scale = (percent) =>
    percent !== undefined ? (percent / 10).toFixed(1) : '—';
  const formatShortDate = (dateString) =>
    dateString
      ? new Date(dateString).toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' })
      : '';

  const totalDeadlines = deadlines.length;
  const overdueCount = deadlines.filter((d) => d.daysLeft < 0).length;
  const todayCount = deadlines.filter((d) => d.daysLeft === 0).length;
  const nextDeadline = deadlines
    .filter((d) => d.daysLeft >= 0)
    .sort((a, b) => a.daysLeft - b.daysLeft)[0];

  return (
    <div className="home-page">
      <div className="welcome-section">
        <div className="welcome-content">
          <h1>Добро пожаловать, {profile?.full_name || profile?.username || 'Гость'}!</h1>
          <p className="welcome-subtitle">
            Продолжайте изучать веб-разработку. Сегодня отличный день для обучения!
          </p>
          <div className="stats-cards">
            <div className="stat-card">
              <div className="stat-info">
                <div className="stat-value">{getAverageScoreIn10Scale(stats.averageScore)}</div>
                <div className="stat-label">Средний балл</div>
              </div>
            </div>
            <div className="stat-card">
              <div className="stat-info">
                <div className="stat-value">
                  {stats.completedTests}/{stats.totalTests}
                </div>
                <div className="stat-label">Тестов пройдено</div>
              </div>
            </div>
            <div className="stat-card">
              <div className="stat-info">
                <div className="stat-value">{stats.totalPoints}</div>
                <div className="stat-label">Всего баллов</div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="streak-section">
        <h2 className="section-title">Текущий стрик: {stats.streakDays} дней</h2>
        <div className="streak-calendar">
          <div className="streak-placeholder">Продолжайте учиться каждый день! 🔥</div>
        </div>
        <p className="streak-motivation">
          {stats.streakDays >= 7
            ? 'Отличная работа! Продолжайте в том же духе!'
            : 'Пройдите тест сегодня, чтобы продолжить стрик!'}
        </p>
      </div>

      <div className="tabs-navigation">
        <button
          className={`tab-btn ${activeTab === 'roadmap' ? 'active' : ''}`}
          onClick={() => setActiveTab('roadmap')}
        >
          Дорожная карта
        </button>
        <button
          className={`tab-btn ${activeTab === 'deadlines' ? 'active' : ''}`}
          onClick={() => setActiveTab('deadlines')}
        >
          Ближайшие дедлайны
        </button>
        <button
          className={`tab-btn ${activeTab === 'progress' ? 'active' : ''}`}
          onClick={() => setActiveTab('progress')}
        >
          Прогресс
        </button>
      </div>

      <div className="tab-content">
        {activeTab === 'roadmap' && (
          <div className="roadmap-section">
            <h2 className="section-title">Дорожная карта обучения</h2>
            {levels?.length ? (
              <div className="roadmap-timeline">
                {levels.map((level, idx) => {
                  const isCompleted =
                    currentLevel && level.required_points <= currentLevel.required_points;
                  const isCurrent = currentLevel && level.id === currentLevel.id;
                  return (
                    <div
                      key={level.id}
                      className={`roadmap-item ${isCompleted ? 'completed' : isCurrent ? 'in_progress' : 'pending'}`}
                    >
                      <div className="roadmap-marker">
                        {idx < levels.length - 1 && <div className="timeline-line"></div>}
                      </div>
                      <div className="roadmap-content">
                        <div className="roadmap-header">
                          <h3>{level.name}</h3>
                          <span
                            className={`status-badge ${isCompleted ? 'completed' : isCurrent ? 'in_progress' : 'pending'}`}
                          >
                            {isCompleted ? 'Завершено' : isCurrent ? 'В процессе' : 'Ожидает'}
                          </span>
                        </div>
                        <p className="roadmap-description">
                          {level.description || `Требуется ${level.required_points} баллов`}
                        </p>
                        <div className="roadmap-details">
                          <div className="detail">
                            <span className="detail-label">Необходимо баллов:</span>
                            <span className="detail-value">{level.required_points}</span>
                          </div>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            ) : (
              <p>Нет данных о уровнях</p>
            )}
          </div>
        )}

        {activeTab === 'deadlines' && (
          <div className="deadlines-section">
            <h2 className="section-title">Ближайшие дедлайны</h2>
            <div className="deadline-stats">
              <div className="stat-big-card">
                <span className="stat-big-value">{totalDeadlines}</span>
                <span className="stat-big-label">Всего заданий</span>
              </div>
              <div className="stat-big-card overdue">
                <span className="stat-big-value">{overdueCount}</span>
                <span className="stat-big-label">Просрочено</span>
              </div>
              <div className="stat-big-card today">
                <span className="stat-big-value">{todayCount}</span>
                <span className="stat-big-label">На сегодня</span>
              </div>
            </div>
            {nextDeadline && (
              <div className="deadline-timer">
                <span className="timer-label">Ближайший дедлайн</span>
                <span className="timer-value">
                  {nextDeadline.title} — {nextDeadline.daysLeft} дн.
                </span>
              </div>
            )}
            <div className="deadlines-filters">
              <button
                className={`filter-btn ${activeFilter === 'all' ? 'active' : ''}`}
                onClick={() => setActiveFilter('all')}
              >
                Все
              </button>
              <button
                className={`filter-btn ${activeFilter === 'test' ? 'active' : ''}`}
                onClick={() => setActiveFilter('test')}
              >
                Тесты
              </button>
            </div>
            <div className="deadlines-horizontal">
              {deadlines
                .filter((d) => activeFilter === 'all' || d.type === activeFilter)
                .map((item) => (
                  <div
                    key={item.id}
                    className={`deadline-item-horizontal priority-${item.priority}`}
                  >
                    <div className="deadline-info-horizontal">
                      <div className="deadline-title-horizontal">{item.title}</div>
                      <div className="deadline-meta-horizontal">
                        <span className="deadline-date">{formatShortDate(item.deadline)}</span>
                        <span
                          className={`deadline-days-left ${item.daysLeft <= 3 ? 'urgent' : ''}`}
                        >
                          {item.daysLeft}{' '}
                          {item.daysLeft === 1 ? 'день' : item.daysLeft <= 4 ? 'дня' : 'дней'}
                        </span>
                      </div>
                    </div>
                  </div>
                ))}
              {!deadlines.length && <p>Нет заданий с дедлайнами</p>}
            </div>
          </div>
        )}

        {activeTab === 'progress' && (
          <div className="progress-section">
            <h2 className="section-title">Ваш прогресс обучения</h2>
            <div className="progress-stats" style={{ gridTemplateColumns: 'repeat(2, 1fr)' }}>
              <div className="progress-stat">
                <div
                  className="stat-circle"
                  style={{
                    background: `conic-gradient(#667eea ${(stats.completedTests / (stats.totalTests || 1)) * 360}deg, #e0e7ff 0deg)`,
                  }}
                >
                  <span>
                    {stats.totalTests
                      ? Math.round((stats.completedTests / stats.totalTests) * 100)
                      : 0}
                    %
                  </span>
                </div>
                <p>Тестов пройдено</p>
              </div>
              <div className="progress-stat">
                <div
                  className="stat-circle"
                  style={{
                    background: `conic-gradient(#52c41a ${(stats.totalPoints / 1000) * 360}deg, #e0e7ff 0deg)`,
                  }}
                >
                  <span>{stats.totalPoints}</span>
                </div>
                <p>Всего баллов</p>
              </div>
            </div>
            <div className="achievements">
              <h3>Достижения</h3>
              <div className="achievements-grid">
                {badges.length === 0 && (
                  <p>Пока нет достижений. Проходите тесты, чтобы их получить!</p>
                )}
                {badges.map((badge) => (
                  <div
                    key={badge.code}
                    className={`achievement ${badge.earned ? 'earned' : 'locked'}`}
                  >
                    <div className="achievement-info">
                      <h4>{badge.title}</h4>
                      <p>{badge.description}</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}
      </div>

      <div className="quick-actions">
        <h2 className="section-title">Быстрые действия</h2>
        <div className="actions-grid">
          <Link to="/tests" className="action-card">
            <div className="action-content">
              <h3>Продолжить тест</h3>
              <p>Проверьте свои знания</p>
            </div>
          </Link>
          <Link to="/materials" className="action-card">
            <div className="action-content">
              <h3>Новые материалы</h3>
              <p>Изучайте теорию</p>
            </div>
          </Link>
          <Link to="/analytics" className="action-card">
            <div className="action-content">
              <h3>Аналитика</h3>
              <p>Посмотрите прогресс</p>
            </div>
          </Link>
        </div>
      </div>
    </div>
  );
};

export default Home;
