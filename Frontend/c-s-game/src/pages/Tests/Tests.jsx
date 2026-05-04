import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { fetchTestContent, fetchTests, fetchTestsCatalogMe, fetchUserAnswers, fetchTestAttemptsQuota } from '../../api/api';
import './Tests.css';

const Tests = () => {
  const [tests, setTests] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [userScores, setUserScores] = useState({});
  const [questionsCount, setQuestionsCount] = useState({});
  const [attemptsQuota, setAttemptsQuota] = useState({});

  useEffect(() => {
    const loadLegacyTests = async () => {
      const data = await fetchTests();
      setTests(data);

      const countMap = {};
      await Promise.all(
        data.map(async (test) => {
          try {
            const content = await fetchTestContent(test.id);
            countMap[test.id] = content.questions.length;
          } catch {
            console.warn(`Не удалось загрузить вопросы для теста ${test.id}`);
          }
        })
      );
      setQuestionsCount(countMap);

      const scoresMap = {};
      await Promise.all(
        data.map(async (test) => {
          try {
            const answers = await fetchUserAnswers(test.id);
            if (answers && answers.length > 0) {
              const userScore = answers.reduce((sum, ans) => sum + (ans.score || 0), 0);
              scoresMap[test.id] = { userScore, maxScore: test.max_score };
            }
          } catch {
            console.warn(`Не удалось загрузить ответы для теста ${test.id}`);
          }
        })
      );
      setUserScores(scoresMap);

      const quotaMap = {};
      await Promise.all(
        data.map(async (test) => {
          try {
            const quota = await fetchTestAttemptsQuota(test.id);
            quotaMap[test.id] = quota;
          } catch {
            console.warn(`Не удалось загрузить квоту для теста ${test.id}`);
          }
        })
      );
      setAttemptsQuota(quotaMap);
    };

    const loadCatalogTests = async () => {
      const data = await fetchTestsCatalogMe();
      if (!Array.isArray(data)) {
        throw new Error('Неожиданный формат ответа каталога тестов');
      }
      setTests(data);

      const countMap = {};
      const scoresMap = {};
      const quotaMap = {};
      await Promise.all(
        data.map(async (test) => {
          if (typeof test.total_questions === 'number') {
            countMap[test.id] = test.total_questions;
          }
          if (test.user_score !== null && test.user_score !== undefined) {
            scoresMap[test.id] = {
              userScore: test.user_score,
              maxScore: test.user_max_score ?? test.max_score,
            };
          }
          try {
            const quota = await fetchTestAttemptsQuota(test.id);
            quotaMap[test.id] = quota;
          } catch {
            console.warn(`Не удалось загрузить квоту для теста ${test.id}`);
          }
        })
      );
      setQuestionsCount(countMap);
      setUserScores(scoresMap);
      setAttemptsQuota(quotaMap);
    };

    const loadTests = async () => {
      try {
        await loadCatalogTests();
      } catch (catalogErr) {
        console.warn('Не удалось загрузить /tests/catalog/me, используем старый метод');
        try {
          await loadLegacyTests();
        } catch (legacyErr) {
          setError(legacyErr.message || catalogErr.message);
        }
      } finally {
        setLoading(false);
      }
    };

    loadTests();
  }, []);

  const getUserStatus = (test) => {
    if (test.user_status) return test.user_status;
    return userScores[test.id] !== undefined ? 'completed' : 'not_started';
  };

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
    const userStatus = getUserStatus(test);

    if (userStatus === 'completed') return { text: 'Завершен', class: 'status-completed' };
    if (userStatus === 'in_progress') return { text: 'В процессе', class: 'status-in-progress' };
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
            <div className="test-stat-value">{tests.filter((t) => getUserStatus(t) === 'completed').length}</div>
            <div className="test-stat-label">Завершено</div>
          </div>
        </div>
        <div className="test-stat-card">
          <div className="test-stat-info">
            <div className="test-stat-value">{tests.filter((t) => t.time_limit_minutes).length}</div>
            <div className="test-stat-label">С ограничением времени</div>
          </div>
        </div>
      </div>

      <div className="tests-grid">
        {tests.map((test) => {
          const statusBadge = getStatusBadge(test);
          const userStatus = getUserStatus(test);
          const scoreInfo =
            userScores[test.id] ||
            (test.user_score !== null && test.user_score !== undefined
              ? {
                  userScore: test.user_score,
                  maxScore: test.user_max_score ?? test.max_score,
                }
              : undefined);
          const userScore = scoreInfo?.userScore;
          const maxScore = scoreInfo?.maxScore ?? test.max_score ?? test.user_max_score;
          const totalQuestions = questionsCount[test.id] ?? test.total_questions ?? '?';
          const quota = attemptsQuota[test.id];
          const attemptsText = quota
            ? `${quota.used_attempts || 0}/${quota.max_attempts || '∞'}`
            : '';

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
                    <span className="stat-value">{totalQuestions}</span>
                  </div>
                  <div className="stat-detail">
                    <span className="stat-label">Макс. баллы:</span>
                    <span className="stat-value">{maxScore ?? '?'}</span>
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
                        {userScore}/{maxScore ?? '?'}
                        {maxScore ? (
                          <span className="score-percentage">
                            ({Math.round((userScore / maxScore) * 100)}%)
                          </span>
                        ) : null}
                      </span>
                    </div>
                  )}
                  {attemptsText && (
                    <div className="stat-detail">
                      <span className="stat-label">Попытки:</span>
                      <span className="stat-value">{attemptsText}</span>
                    </div>
                  )}
                </div>
              </div>

              <div className="test-footer">
                <div className="test-actions">
                  {userStatus === 'completed' ? (
                    <button className="action-btn retry-btn" disabled>
                      Пройти заново
                    </button>
                  ) : userStatus === 'in_progress' ? (
                    <Link to={`/test/${test.id}`} className="action-btn start-btn">
                      Продолжить
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
    </div>
  );
};

export default Tests;