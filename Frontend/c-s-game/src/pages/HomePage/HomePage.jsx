import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import './HomePage.css';

const Home = () => {
  const [stats, setStats] = useState({
    totalTests: 8,
    completed: 3,
    inProgress: 2,
    pending: 3,
    averageScore: 78,
    totalPoints: 1250,
    streakDays: 7,
    nextDeadline: '2024-03-15',
  });

  const [roadmap, setRoadmap] = useState([
    {
      id: 1,
      title: 'HTML/CSS основы',
      description: 'Основы верстки и стилизации',
      status: 'completed',
      deadline: '2024-02-28',
      tests: 3,
      materials: 5,
      progress: 100,
    },
    {
      id: 2,
      title: 'JavaScript ES6+',
      description: 'Современный JavaScript',
      status: 'completed',
      deadline: '2024-03-05',
      tests: 4,
      materials: 8,
      progress: 100,
    },
    {
      id: 3,
      title: 'React.js основы',
      description: 'Библиотека для создания UI',
      status: 'in_progress',
      deadline: '2024-03-15',
      tests: 5,
      materials: 10,
      progress: 65,
    },
    {
      id: 4,
      title: 'React Router & State',
      description: 'Навигация и управление состоянием',
      status: 'in_progress',
      deadline: '2024-03-25',
      tests: 4,
      materials: 7,
      progress: 30,
    },
    {
      id: 5,
      title: 'Node.js & Express',
      description: 'Серверный JavaScript',
      status: 'pending',
      deadline: '2024-04-10',
      tests: 6,
      materials: 12,
      progress: 0,
    },
    {
      id: 6,
      title: 'Базы данных (SQL/NoSQL)',
      description: 'Работа с данными',
      status: 'pending',
      deadline: '2024-04-25',
      tests: 5,
      materials: 9,
      progress: 0,
    },
    {
      id: 7,
      title: 'Deploy & DevOps основы',
      description: 'Развертывание приложений',
      status: 'pending',
      deadline: '2024-05-10',
      tests: 3,
      materials: 6,
      progress: 0,
    },
  ]);

  const [deadlines, setDeadlines] = useState([
    {
      id: 1,
      title: 'React.js основы - тест',
      type: 'test',
      deadline: '2024-03-15',
      daysLeft: 3,
      priority: 'high',
    },
    {
      id: 2,
      title: 'React Router - практическое задание',
      type: 'practice',
      deadline: '2024-03-20',
      daysLeft: 8,
      priority: 'medium',
    },
    {
      id: 3,
      title: "Проект 'Туду лист'",
      type: 'project',
      deadline: '2024-03-25',
      daysLeft: 13,
      priority: 'high',
    },
    {
      id: 4,
      title: 'Node.js основы - тест',
      type: 'test',
      deadline: '2024-03-25',
      daysLeft: 13,
      priority: 'medium',
    },
    {
      id: 5,
      title: 'Express.js - middleware задание',
      type: 'practice',
      deadline: '2024-04-05',
      daysLeft: 24,
      priority: 'low',
    },
  ]);

  const [streak, setStreak] = useState([
    { day: 'Пн', date: '4', active: true },
    { day: 'Вт', date: '5', active: true },
    { day: 'Ср', date: '6', active: true },
    { day: 'Чт', date: '7', active: true },
    { day: 'Пт', date: '8', active: true },
    { day: 'Сб', date: '9', active: true },
    { day: 'Вс', date: '10', active: true },
    { day: 'Пн', date: '11', active: false },
    { day: 'Вт', date: '12', active: false },
    { day: 'Ср', date: '13', active: false },
    { day: 'Чт', date: '14', active: false },
    { day: 'Пт', date: '15', active: false },
    { day: 'Сб', date: '16', active: false },
    { day: 'Вс', date: '17', active: false },
  ]);

  const [activeTab, setActiveTab] = useState('roadmap');
  const [activeFilter, setActiveFilter] = useState('all');

  const totalDeadlines = deadlines.length;
  const overdueCount = deadlines.filter((d) => d.daysLeft < 0).length;
  const todayCount = deadlines.filter((d) => d.daysLeft === 0).length;

  const nextDeadline = deadlines
    .filter((d) => d.daysLeft >= 0)
    .reduce((prev, curr) => (curr.daysLeft < prev.daysLeft ? curr : prev), deadlines[0]);

  const formatDate = (dateString) => {
    const date = new Date(dateString);
    return date.toLocaleDateString('ru-RU', {
      day: 'numeric',
      month: 'long',
    });
  };

  const formatShortDate = (dateString) => {
    const date = new Date(dateString);
    return date.toLocaleDateString('ru-RU', {
      day: 'numeric',
      month: 'short',
    });
  };

  const getPriorityClass = (priority) => {
    switch (priority) {
      case 'high':
        return 'priority-high';
      case 'medium':
        return 'priority-medium';
      case 'low':
        return 'priority-low';
      default:
        return '';
    }
  };

  const getFilteredDeadlines = () => {
    if (activeFilter === 'all') return deadlines;
    return deadlines.filter((item) => item.type === activeFilter);
  };

  return (
    <div className="home-page">
      <div className="welcome-section">
        <div className="welcome-content">
          <h1>Добро пожаловать, Алексей!</h1>
          <p className="welcome-subtitle">
            Продолжайте изучать веб-разработку. Сегодня отличный день для обучения!
          </p>

          <div className="stats-cards">
            <div className="stat-card">
              <div className="stat-info">
                <div className="stat-value">{stats.streakDays} дней</div>
                <div className="stat-label">Текущий стрик</div>
              </div>
            </div>

            <div className="stat-card">
              <div className="stat-info">
                <div className="stat-value">{stats.averageScore}%</div>
                <div className="stat-label">Средний балл</div>
              </div>
            </div>

            <div className="stat-card">
              <div className="stat-info">
                <div className="stat-value">
                  {stats.completed}/{stats.totalTests}
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

      {/* Стрик */}
      <div className="streak-section">
        <h2 className="section-title">Текущий стрик: {stats.streakDays} дней</h2>
        <div className="streak-calendar">
          {streak.map((day, index) => (
            <div
              key={index}
              className={`streak-day ${day.active ? 'active' : ''} ${index === 6 ? 'current' : ''}`}
            >
              <div className="streak-day-label">{day.day}</div>
              <div className="streak-day-date">{day.date}</div>
              {day.active && <div className="streak-day-fire">🔥</div>}
            </div>
          ))}
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
            <div className="roadmap-timeline">
              {roadmap.map((item, index) => (
                <div key={item.id} className={`roadmap-item ${item.status}`}>
                  <div className="roadmap-marker">
                    {index < roadmap.length - 1 && <div className="timeline-line"></div>}
                  </div>

                  <div className="roadmap-content">
                    <div className="roadmap-header">
                      <h3>{item.title}</h3>
                      <span className={`status-badge ${item.status}`}>
                        {item.status === 'completed'
                          ? 'Завершено'
                          : item.status === 'in_progress'
                            ? 'В процессе'
                            : 'Ожидает'}
                      </span>
                    </div>

                    <p className="roadmap-description">{item.description}</p>

                    <div className="roadmap-details">
                      <div className="detail">
                        <span className="detail-label">Дедлайн:</span>
                        <span className="detail-value">{formatDate(item.deadline)}</span>
                      </div>

                      <div className="detail">
                        <span className="detail-label">Тестов:</span>
                        <span className="detail-value">{item.tests}</span>
                      </div>

                      <div className="detail">
                        <span className="detail-label">Материалов:</span>
                        <span className="detail-value">{item.materials}</span>
                      </div>
                    </div>

                    <div className="progress-container">
                      <div className="progress-bar">
                        <div className="progress-fill" style={{ width: `${item.progress}%` }}></div>
                      </div>
                      <span className="progress-text">{item.progress}%</span>
                    </div>

                    <div className="roadmap-actions">
                      {item.status === 'completed' ? (
                        <button className="action-btn review-btn">Обзор результатов</button>
                      ) : item.status === 'in_progress' ? (
                        <Link to="/tests" className="action-btn continue-btn">
                          Продолжить обучение
                        </Link>
                      ) : (
                        <button className="action-btn start-btn" disabled>
                          Скоро будет доступно
                        </button>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
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
              <button
                className={`filter-btn ${activeFilter === 'practice' ? 'active' : ''}`}
                onClick={() => setActiveFilter('practice')}
              >
                Задания
              </button>
              <button
                className={`filter-btn ${activeFilter === 'project' ? 'active' : ''}`}
                onClick={() => setActiveFilter('project')}
              >
                Проекты
              </button>
            </div>

            <div className="deadlines-horizontal">
              {getFilteredDeadlines().map((item) => (
                <div
                  key={item.id}
                  className={`deadline-item-horizontal ${getPriorityClass(item.priority)}`}
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
            </div>

            <div className="calendar-preview">
              <h3>Март 2024</h3>
              <div className="calendar-grid">
                {['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'].map((day) => (
                  <div key={day} className="calendar-day-header">
                    {day}
                  </div>
                ))}
                {Array.from({ length: 31 }, (_, i) => i + 1).map((day) => {
                  const hasDeadline = deadlines.some((d) => new Date(d.deadline).getDate() === day);
                  return (
                    <div key={day} className={`calendar-day ${hasDeadline ? 'has-deadline' : ''}`}>
                      {day}
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        )}

        {activeTab === 'progress' && (
          <div className="progress-section">
            <h2 className="section-title">Ваш прогресс обучения</h2>

            <div className="progress-overview">
              <div className="progress-chart">
                <div className="chart-header">
                  <h3>Общий прогресс курса</h3>
                  <span className="chart-percentage">42%</span>
                </div>
                <div className="chart-bar">
                  <div className="chart-fill" style={{ width: '42%' }}></div>
                </div>
              </div>

              <div className="progress-stats">
                <div className="progress-stat">
                  <div
                    className="stat-circle"
                    style={{ background: 'conic-gradient(#667eea 180deg, #e0e7ff 0deg)' }}
                  >
                    <span>50%</span>
                  </div>
                  <p>Тестов пройдено</p>
                </div>

                <div className="progress-stat">
                  <div
                    className="stat-circle"
                    style={{ background: 'conic-gradient(#52c41a 65deg, #e0e7ff 0deg)' }}
                  >
                    <span>18%</span>
                  </div>
                  <p>Заданий выполнено</p>
                </div>

                <div className="progress-stat">
                  <div
                    className="stat-circle"
                    style={{ background: 'conic-gradient(#fa8c16 240deg, #e0e7ff 0deg)' }}
                  >
                    <span>67%</span>
                  </div>
                  <p>Материалов изучено</p>
                </div>
              </div>
            </div>

            <div className="skills-breakdown">
              <h3>Распределение навыков</h3>
              <div className="skills-grid">
                <div className="skill-item">
                  <div className="skill-header">
                    <span className="skill-name">HTML/CSS</span>
                    <span className="skill-score">92%</span>
                  </div>
                  <div className="skill-bar">
                    <div className="skill-fill" style={{ width: '92%' }}></div>
                  </div>
                </div>

                <div className="skill-item">
                  <div className="skill-header">
                    <span className="skill-name">JavaScript</span>
                    <span className="skill-score">78%</span>
                  </div>
                  <div className="skill-bar">
                    <div className="skill-fill" style={{ width: '78%' }}></div>
                  </div>
                </div>

                <div className="skill-item">
                  <div className="skill-header">
                    <span className="skill-name">React.js</span>
                    <span className="skill-score">65%</span>
                  </div>
                  <div className="skill-bar">
                    <div className="skill-fill" style={{ width: '65%' }}></div>
                  </div>
                </div>

                <div className="skill-item">
                  <div className="skill-header">
                    <span className="skill-name">Node.js</span>
                    <span className="skill-score">30%</span>
                  </div>
                  <div className="skill-bar">
                    <div className="skill-fill" style={{ width: '30%' }}></div>
                  </div>
                </div>

                <div className="skill-item">
                  <div className="skill-header">
                    <span className="skill-name">Базы данных</span>
                    <span className="skill-score">15%</span>
                  </div>
                  <div className="skill-bar">
                    <div className="skill-fill" style={{ width: '15%' }}></div>
                  </div>
                </div>
              </div>
            </div>

            <div className="achievements">
              <h3>Достижения</h3>
              <div className="achievements-grid">
                <div className="achievement earned">
                  <div className="achievement-info">
                    <h4>7-дневный стрик</h4>
                    <p>Занимайтесь 7 дней подряд</p>
                  </div>
                </div>

                <div className="achievement earned">
                  <div className="achievement-info">
                    <h4>Быстрый старт</h4>
                    <p>Пройдите 3 теста за первую неделю</p>
                  </div>
                </div>

                <div className="achievement locked">
                  <div className="achievement-info">
                    <h4>Отличник</h4>
                    <p>Наберите 90%+ в 5 тестах</p>
                  </div>
                </div>

                <div className="achievement locked">
                  <div className="achievement-info">
                    <h4>Мастер React</h4>
                    <p>Завершите все React тесты</p>
                  </div>
                </div>
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
              <p>React.js основы - 65% пройдено</p>
            </div>
          </Link>

          <Link to="/materials" className="action-card">
            <div className="action-content">
              <h3>Новые материалы</h3>
              <p>3 новых урока доступны</p>
            </div>
          </Link>

          <div className="action-card">
            <div className="action-content">
              <h3>Цель дня</h3>
              <p>Пройти 1 тест для сохранения стрика</p>
            </div>
          </div>

          <div className="action-card">
            <div className="action-content">
              <h3>Аналитика</h3>
              <p>Посмотреть ваш прогресс за неделю</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Home;
