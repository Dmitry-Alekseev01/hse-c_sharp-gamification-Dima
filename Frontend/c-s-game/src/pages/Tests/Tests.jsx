import React, { useEffect, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { fetchTestsCatalogMe } from '../../api/api';
import './Tests.css';

const Tests = () => {
  const [tests, setTests] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const location = useLocation();

  const loadTests = async () => {
    setLoading(true);
    try {
      const data = await fetchTestsCatalogMe();
      if (!Array.isArray(data)) {
        throw new Error('Неожиданный формат ответа каталога тестов');
      }
      setTests(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadTests();
  }, [location.key]);

  const formatDate = (dateString) => {
    if (!dateString) return '';
    const date = new Date(dateString);
    return date.toLocaleDateString('ru-RU', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
    });
  };

  const formatDateTime = (dateString) => {
    if (!dateString) return '';
    const date = new Date(dateString);
    return date.toLocaleDateString('ru-RU', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  const getStatusBadge = (test) => {
    const now = new Date();
    const deadlineDate = test.deadline ? new Date(test.deadline) : null;
    const state = test.attempt_state;

    if (state === 'completed') return { text: 'Завершен', class: 'status-completed' };
    if (state === 'in_progress') return { text: 'В процессе', class: 'status-in-progress' };
    if (deadlineDate && now > deadlineDate) return { text: 'Просрочен', class: 'status-overdue' };
    return { text: 'Не начат', class: 'status-not-started' };
  };

  if (loading) return <div className="loading">Загрузка тестов...</div>;
  if (error) return <div className="error">Ошибка: {error}</div>;

  return (
    <div className="tests-page">
      <div className="tests-header">
        <h1>Тесты и проверка знаний</h1>
        <p className="tests-subtitle">Пройдите тесты для проверки усвоения материалов</p>
      </div>

      <div className="tests-stats">
        <div className="test-stat-card">
          <div className="test-stat-info">
            <div className="test-stat-value">{tests.length}</div>
            <div className="test-stat-label">Всего тестов</div>
          </div>
        </div>
        <div className="test-stat-card">
          <div className="test-stat-info">
            <div className="test-stat-value">{tests.filter(t => t.attempt_state === 'completed').length}</div>
            <div className="test-stat-label">Завершено</div>
          </div>
        </div>
        <div className="test-stat-card">
          <div className="test-stat-info">
            <div className="test-stat-value">{tests.filter(t => t.time_limit_minutes).length}</div>
            <div className="test-stat-label">С ограничением времени</div>
          </div>
        </div>
      </div>

      <div className="tests-grid">
        {tests.map((test) => {
          const statusBadge = getStatusBadge(test);
          const completedAttempts = test.completed_attempts ?? 0;
          const hasActive = Boolean(test.has_active_attempt);
          const usedAttempts = completedAttempts + (hasActive ? 1 : 0);
          const maxAttempts = test.max_attempts ?? '∞';
          const attemptsText = maxAttempts === '∞' ? `${usedAttempts}/∞` : `${usedAttempts}/${maxAttempts}`;

          const renderAction = () => {
            if (test.attempt_state === 'blocked') {
              return <button className="action-btn retry-btn" disabled>Недоступно</button>;
            }
            if (test.attempt_state === 'in_progress') {
              return <Link to={`/test/${test.id}`} className="action-btn start-btn">Продолжить</Link>;
            }
            return (
              <Link to={`/test/${test.id}`} className="action-btn start-btn">
                {completedAttempts > 0 ? 'Пройти заново' : 'Начать тест'}
              </Link>
            );
          };

          return (
            <div key={test.id} className="test-card">
              <div className="test-header">
                <div className="test-title-section">
                  <h2 className="test-title">{test.title}</h2>
                  <span className={`status-badge ${statusBadge.class}`}>{statusBadge.text}</span>
                </div>
                <div className="test-meta">
                  {test.deadline && (
                    <div className="meta-item">
                      <span className="meta-label">Дедлайн:</span>
                      <span className="meta-value">{formatDateTime(test.deadline)}</span>
                    </div>
                  )}
                  {test.published_at && (
                    <div className="meta-item">
                      <span className="meta-label">Опубликован:</span>
                      <span className="meta-value">{formatDate(test.published_at)}</span>
                    </div>
                  )}
                </div>
              </div>

              <div className="test-content">
                <div className="test-stats-details">
                  <div className="stat-detail">
                    <span className="stat-label">Вопросов:</span>
                    <span className="stat-value">{test.total_questions ?? '?'}</span>
                  </div>
                  <div className="stat-detail">
                    <span className="stat-label">Макс. баллы:</span>
                    <span className="stat-value">{test.max_score ?? '?'}</span>
                  </div>
                  {test.time_limit_minutes && (
                    <div className="stat-detail">
                      <span className="stat-label">Время:</span>
                      <span className="stat-value">{test.time_limit_minutes} мин.</span>
                    </div>
                  )}
                  <div className="stat-detail">
                    <span className="stat-label">Результат:</span>
                    <span className="stat-value">
                      {test.user_score ?? 0}/{test.max_score ?? '?'}
                      {test.max_score && test.user_score != null && (
                        <span className="score-percentage">
                          ({Math.round((test.user_score / test.max_score) * 100)}%)
                        </span>
                      )}
                    </span>
                  </div>
                  <div className="stat-detail">
                    <span className="stat-label">Попытки:</span>
                    <span className="stat-value">{attemptsText}</span>
                  </div>
                </div>
              </div>

              <div className="test-footer">
                <div className="test-actions">
                  {renderAction()}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default Tests;