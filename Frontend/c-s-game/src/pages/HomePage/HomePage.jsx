import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import {
  fetchUserProfile,
  getToken,
  fetchUserProgress,
  fetchTests,
  fetchMaterials,
  fetchLevels,
  fetchUserAnswers,
} from '../../api/api';
import './HomePage.css';

const Home = () => {
  const [loading, setLoading] = useState(true);
  const [userName, setUserName] = useState('');
  const [stats, setStats] = useState({
    totalTests: 0,
    completedTests: 0,
    averageScore: 0,
    totalPoints: 0,
    streakDays: 0,
    totalMaterials: 0,
  });
  const [levels, setLevels] = useState([]);
  const [currentLevel, setCurrentLevel] = useState(null);
  const [deadlines, setDeadlines] = useState([]);
  const [badges, setBadges] = useState([]);
  const [activeTab, setActiveTab] = useState('roadmap');
  const [activeFilter, setActiveFilter] = useState('all');

  const getAverageScoreIn10Scale = (percent) => {
    if (percent === undefined || percent === null) return '—';
    const score = (percent / 10).toFixed(1);
    return score;
  };

  const formatDate = (dateString) => {
    if (!dateString) return '';
    const date = new Date(dateString);
    return date.toLocaleDateString('ru-RU', { day: 'numeric', month: 'long' });
  };

  const formatShortDate = (dateString) => {
    if (!dateString) return '';
    const date = new Date(dateString);
    return date.toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' });
  };

  const getPriorityClass = (daysLeft) => {
    if (daysLeft <= 3) return 'priority-high';
    if (daysLeft <= 7) return 'priority-medium';
    return 'priority-low';
  };

  const getFilteredDeadlines = () => {
    if (activeFilter === 'all') return deadlines;
    return deadlines.filter((item) => item.type === activeFilter);
  };

  useEffect(() => {
    const loadHomeData = async () => {
      if (!getToken()) {
        setLoading(false);
        return;
      }
      try {
        const profile = await fetchUserProfile();
        setUserName(profile.full_name || profile.username);

        const progress = await fetchUserProgress(profile.id);
        if (progress) {
          setStats((prev) => ({
            ...prev,
            totalPoints: progress.total_points || 0,
            streakDays: progress.streak_days || 0,
          }));
          setBadges(progress.badges || []);
          if (progress.current_level) setCurrentLevel(progress.current_level);
        }

        const levelsData = await fetchLevels();
        setLevels(levelsData || []);

        const tests = await fetchTests();
        const totalTestsCount = tests.length;
        let completedCount = 0;
        let totalScoreSum = 0;
        let testsWithScore = 0;
        const deadlinesList = [];

        for (const test of tests) {
          if (test.deadline) {
            const deadlineDate = new Date(test.deadline);
            const today = new Date();
            const diffTime = deadlineDate - today;
            const daysLeft = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
            deadlinesList.push({
              id: test.id,
              title: test.title,
              type: 'test',
              deadline: test.deadline,
              daysLeft: daysLeft,
              priority: daysLeft <= 3 ? 'high' : daysLeft <= 7 ? 'medium' : 'low',
            });
          }

          try {
            const answers = await fetchUserAnswers(test.id);
            if (answers && answers.length > 0) {
              completedCount++;
              const userScore = answers.reduce((sum, ans) => sum + (ans.score || 0), 0);
              const maxScore = test.max_score;
              if (maxScore) {
                const percentage = (userScore / maxScore) * 100;
                totalScoreSum += percentage;
                testsWithScore++;
              }
            }
          } catch (e) {}
        }

        const averageScore = testsWithScore > 0 ? Math.round(totalScoreSum / testsWithScore) : 0;
        setStats((prev) => ({
          ...prev,
          totalTests: totalTestsCount,
          completedTests: completedCount,
          averageScore: averageScore,
        }));
        setDeadlines(deadlinesList);

        const materials = await fetchMaterials();
        setStats((prev) => ({
          ...prev,
          totalMaterials: materials.length,
        }));
      } catch (error) {
        console.error('Ошибка загрузки главной страницы:', error);
      } finally {
        setLoading(false);
      }
    };
    loadHomeData();
  }, []);

  if (loading) return <div className="loading">Загрузка...</div>;

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
          <h1>Добро пожаловать, {userName || 'Гость'}!</h1>
          <p className="welcome-subtitle">
            Продолжайте изучать веб-разработку. Сегодня отличный день для обучения!
          </p>
          <div className="stats-cards">
            {/* Убрана карточка "Текущий стрик" */}
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
            {levels.length === 0 ? (
              <p>Нет данных о уровнях</p>
            ) : (
              <div className="roadmap-timeline">
                {levels.map((level, index) => {
                  const isCompleted =
                    currentLevel && level.required_points <= currentLevel.required_points;
                  const isCurrent = currentLevel && level.id === currentLevel.id;
                  return (
                    <div
                      key={level.id}
                      className={`roadmap-item ${isCompleted ? 'completed' : isCurrent ? 'in_progress' : 'pending'}`}
                    >
                      <div className="roadmap-marker">
                        {index < levels.length - 1 && <div className="timeline-line"></div>}
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
              {getFilteredDeadlines().map((item) => (
                <div
                  key={item.id}
                  className={`deadline-item-horizontal ${getPriorityClass(item.daysLeft)}`}
                >
                  <div className="deadline-info-horizontal">
                    <div className="deadline-title-horizontal">{item.title}</div>
                    <div className="deadline-meta-horizontal">
                      <span className="deadline-date">{formatShortDate(item.deadline)}</span>
                      <span className={`deadline-days-left ${item.daysLeft <= 3 ? 'urgent' : ''}`}>
                        {item.daysLeft}{' '}
                        {item.daysLeft === 1 ? 'день' : item.daysLeft <= 4 ? 'дня' : 'дней'}
                      </span>
                    </div>
                  </div>
                </div>
              ))}
              {getFilteredDeadlines().length === 0 && <p>Нет заданий с дедлайнами</p>}
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
