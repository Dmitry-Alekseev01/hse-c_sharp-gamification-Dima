import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { fetchTests, fetchUserAnswers } from '../../api/api';
import './Tests.css';

const Tests = () => {
  const [tests, setTests] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [userScores, setUserScores] = useState({});

  useEffect(() => {
    const loadTests = async () => {
      try {
        const data = await fetchTests();
        setTests(data);
        const scoresMap = {};
        await Promise.all(
          data.map(async (test) => {
            try {
              const answers = await fetchUserAnswers(test.id);
              if (answers && answers.length > 0) {
                const userScore = answers.reduce((sum, ans) => sum + (ans.score || 0), 0);
                scoresMap[test.id] = { userScore, maxScore: test.max_score };
              }
            } catch (e) {
            }
          })
        );
        setUserScores(scoresMap);
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };
    loadTests();
  }, []);

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
    const hasCompleted = userScores[test.id] !== undefined;
    if (hasCompleted) return { text: 'Завершен', class: 'status-completed' };
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
            <div className="test-stat-value">{Object.keys(userScores).length}</div>
            <div className="test-stat-label">Завершено</div>
          </div>
        </div>
        <div className="test-stat-card">
          <div className="test-stat-info">
            <div className="test-stat-value">
              {tests.filter((t) => t.time_limit_minutes).length}
            </div>
            <div className="test-stat-label">С ограничением времени</div>
          </div>
        </div>
      </div>

      <div className="tests-grid">
        {tests.map((test) => {
          const statusBadge = getStatusBadge(test);
          const scoreInfo = userScores[test.id];
          const userScore = scoreInfo?.userScore;
          const maxScore = test.max_score;

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
                    <span className="stat-value">{test.total_questions || '?'}</span>
                  </div>
                  <div className="stat-detail">
                    <span className="stat-label">Макс. баллы:</span>
                    <span className="stat-value">{maxScore}</span>
                  </div>
                  {test.time_limit_minutes && (
                    <div className="stat-detail">
                      <span className="stat-label">Время:</span>
                      <span className="stat-value">{test.time_limit_minutes} мин.</span>
                    </div>
                  )}
                  {userScore !== undefined && (
                    <div className="stat-detail">
                      <span className="stat-label">Результат:</span>
                      <span className="stat-value">
                        {userScore}/{maxScore}
                        <span className="score-percentage">
                          ({Math.round((userScore / maxScore) * 100)}%)
                        </span>
                      </span>
                    </div>
                  )}
                </div>
              </div>

              <div className="test-footer">
                <div className="test-actions">
                  {userScore !== undefined ? (
                    <Link to={`/test/${test.id}`} className="action-btn retry-btn">
                      Пройти заново
                    </Link>
                  ) : (
                    <Link to={`/test/${test.id}`} className="action-btn start-btn">
                      Начать тест
                    </Link>
                  )}
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {/* Блок tests-info полностью удалён */}
    </div>
  );
};

export default Tests;
