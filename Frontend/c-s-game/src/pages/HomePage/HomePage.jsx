import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { getToken, fetchLearningDashboard, fetchLevels, fetchUserProfile } from '../../api/api';
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

  const getAverageScoreIn10Scale = (p) => (p !== undefined ? (p / 10).toFixed(1) : '—');
  const formatShortDate = (s) =>
    s ? new Date(s).toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' }) : '';
  const getPriorityClass = (d) =>
    d <= 3 ? 'priority-high' : d <= 7 ? 'priority-medium' : 'priority-low';
  const getFilteredDeadlines = () =>
    activeFilter === 'all' ? deadlines : deadlines.filter((i) => i.type === activeFilter);

  useEffect(() => {
    const load = async () => {
      if (!getToken()) {
        setLoading(false);
        return;
      }
      try {
        // Загружаем профиль, дашборд и уровни параллельно
        const [profile, dashboard, levelsData] = await Promise.all([
          fetchUserProfile(),
          fetchLearningDashboard(200),
          fetchLevels(),
        ]);

        // Имя пользователя: приоритет – full_name из профиля, затем username, затем из дашборда
        const displayName =
          profile?.full_name || profile?.username || dashboard?.username || 'Гость';
        setUserName(displayName);

        // Суммируем баллы за последние попытки – используем поле score_value (бэкенд)
        const totalPoints = (dashboard.test_results || []).reduce(
          (sum, test) => sum + (test.score_value || 0),
          0
        );

        setStats({
          totalTests: dashboard.total_tests || 0,
          completedTests: dashboard.completed_tests || 0,
          averageScore: Math.round(dashboard.average_score_percent || 0),
          totalPoints,
          streakDays: dashboard.streak_days || 0,
          totalMaterials: dashboard.total_materials || 0,
        });
        setBadges(dashboard.badges || []);
        setCurrentLevel(dashboard.current_level || null);
        setLevels(levelsData || []);

        const now = new Date();
        const deadlinesList = (dashboard.test_results || [])
          .filter((t) => t.deadline)
          .map((t) => {
            const daysLeft = Math.ceil((new Date(t.deadline) - now) / (1000 * 60 * 60 * 24));
            return {
              id: t.test_id,
              title: t.title,
              type: 'test',
              deadline: t.deadline,
              daysLeft,
              priority: daysLeft <= 3 ? 'high' : daysLeft <= 7 ? 'medium' : 'low',
            };
          });
        setDeadlines(deadlinesList);
      } catch (error) {
        console.error('Ошибка загрузки главной страницы:', error);
      } finally {
        setLoading(false);
      }
    };
    load();
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
          <h1>Добро пожаловать, {userName}!</h1>
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
            {levels.length === 0 ? (
              <p>Нет данных о уровнях</p>
            ) : (
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
