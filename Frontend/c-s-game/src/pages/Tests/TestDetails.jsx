import React, { useState, useEffect } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import {
  fetchTestContent,
  startTestAttempt,
  submitAnswer,
  completeTestAttempt,
} from '../../api/api';
import './TestDetails.css';

const TestDetails = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  const [testData, setTestData] = useState(null);
  const [attemptId, setAttemptId] = useState(null);
  const [userAnswers, setUserAnswers] = useState({});
  const [openAnswers, setOpenAnswers] = useState({});
  const [timeLeft, setTimeLeft] = useState(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [testSubmitted, setTestSubmitted] = useState(false);
  const [currentQuestion, setCurrentQuestion] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const loadTest = async () => {
      try {
        const content = await fetchTestContent(id);
        setTestData(content);

        // Начинаем попытку
        const attempt = await startTestAttempt(id);
        setAttemptId(attempt.id);

        // Если есть ограничение по времени, устанавливаем таймер
        if (content.test.time_limit_minutes) {
          setTimeLeft(content.test.time_limit_minutes * 60);
        }

        // Инициализируем ответы
        const initialAnswers = {};
        content.questions.forEach((q) => {
          if (!q.is_open_answer) {
            initialAnswers[q.id] = null;
          }
        });
        setUserAnswers(initialAnswers);

        const initialOpenAnswers = {};
        content.questions.forEach((q) => {
          if (q.is_open_answer) {
            initialOpenAnswers[q.id] = '';
          }
        });
        setOpenAnswers(initialOpenAnswers);
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };
    loadTest();
  }, [id]);

  useEffect(() => {
    let timer;
    if (timeLeft > 0 && !testSubmitted) {
      timer = setInterval(() => {
        setTimeLeft((prev) => prev - 1);
      }, 1000);
    } else if (timeLeft === 0 && !testSubmitted) {
      handleSubmitTest();
    }
    return () => clearInterval(timer);
  }, [timeLeft, testSubmitted]);

  const handleAnswerChange = (questionId, choiceId) => {
    setUserAnswers((prev) => ({ ...prev, [questionId]: choiceId }));
  };

  const handleOpenAnswerChange = (questionId, value) => {
    setOpenAnswers((prev) => ({ ...prev, [questionId]: value }));
  };

  const handleSubmitTest = async () => {
    if (isSubmitting) return;
    setIsSubmitting(true);
    try {
      // Отправляем все ответы
      const allAnswers = [
        ...Object.entries(userAnswers).map(([qId, choiceId]) => ({
          questionId: parseInt(qId),
          payload: String(choiceId),
        })),
        ...Object.entries(openAnswers).map(([qId, text]) => ({
          questionId: parseInt(qId),
          payload: text,
        })),
      ];
      for (const ans of allAnswers) {
        await submitAnswer(parseInt(id), ans.questionId, ans.payload, attemptId);
      }
      // Завершаем попытку
      await completeTestAttempt(attemptId);
      setTestSubmitted(true);
    } catch (err) {
      setError(err.message);
    } finally {
      setIsSubmitting(false);
    }
  };

  const formatTime = (seconds) => {
    const minutes = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  };

  const formatDate = (dateString) => {
    if (!dateString) return '';
    const date = new Date(dateString);
    return date.toLocaleDateString('ru-RU', {
      day: '2-digit',
      month: 'long',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  const calculateProgress = () => {
    if (!testData) return 0;
    const totalQuestions = testData.questions.length;
    const answered =
      Object.values(userAnswers).filter((a) => a !== null).length +
      Object.values(openAnswers).filter((a) => a.trim() !== '').length;
    return Math.round((answered / totalQuestions) * 100);
  };

  if (loading) return <div className="test-loading">Загрузка теста...</div>;
  if (error) return <div className="error">Ошибка: {error}</div>;
  if (!testData) return null;

  const totalQuestions = testData.questions.length;

  return (
    <div className="test-details-page">
      <div className="test-header">
        <div className="header-top">
          <Link to="/tests" className="back-button">
            Назад к тестам
          </Link>
          {testData.test.time_limit_minutes && !testSubmitted && (
            <div className="timer">{formatTime(timeLeft)}</div>
          )}
        </div>
        <h1>{testData.test.title}</h1>
        <div className="test-meta-info">
          {testData.test.deadline && (
            <div className="meta-item">
              <span className="meta-label">Дедлайн:</span>
              <span className="meta-value">{formatDate(testData.test.deadline)}</span>
            </div>
          )}
          <div className="meta-item">
            <span className="meta-label">Макс. баллы:</span>
            <span className="meta-value">{testData.test.max_score}</span>
          </div>
          <div className="meta-item">
            <span className="meta-label">Вопросов:</span>
            <span className="meta-value">{totalQuestions}</span>
          </div>
          {testData.test.time_limit_minutes && (
            <div className="meta-item">
              <span className="meta-label">Лимит времени:</span>
              <span className="meta-value">{testData.test.time_limit_minutes} минут</span>
            </div>
          )}
        </div>
      </div>

      {!testSubmitted ? (
        <>
          <div className="test-progress">
            <div className="progress-info">
              <span>Прогресс: {calculateProgress()}%</span>
              <span>
                Вопрос {currentQuestion + 1} из {totalQuestions}
              </span>
            </div>
            <div className="progress-bar">
              <div className="progress-fill" style={{ width: `${calculateProgress()}%` }} />
            </div>
          </div>

          <div className="test-content">
            <div className="questions-navigation">
              <h3>Навигация по вопросам</h3>
              <div className="question-dots">
                {testData.questions.map((q, idx) => (
                  <button
                    key={q.id}
                    className={`question-dot ${idx === currentQuestion ? 'active' : ''} ${
                      (q.is_open_answer && openAnswers[q.id]?.trim()) ||
                      (!q.is_open_answer && userAnswers[q.id] !== null)
                        ? 'answered'
                        : ''
                    }`}
                    onClick={() => setCurrentQuestion(idx)}
                  >
                    {idx + 1}
                  </button>
                ))}
              </div>
              <button
                className="submit-btn-sidebar"
                onClick={handleSubmitTest}
                disabled={isSubmitting}
              >
                {isSubmitting ? 'Отправка...' : 'Отправить тест на проверку'}
              </button>
            </div>

            <div className="questions-container">
              {testData.questions[currentQuestion].is_open_answer ? (
                <div className="question-card open-question">
                  <div className="question-header">
                    <h3>Вопрос {currentQuestion + 1} (открытый ответ)</h3>
                    <span className="question-points">
                      Баллы: {testData.questions[currentQuestion].points}
                    </span>
                  </div>
                  <div className="question-text">
                    <p>{testData.questions[currentQuestion].text}</p>
                  </div>
                  {testData.questions[currentQuestion].material_urls?.length > 0 && (
                    <div className="question-materials">
                      <h4>Материалы к вопросу:</h4>
                      {testData.questions[currentQuestion].material_urls.map((url, i) => (
                        <a key={i} href={url} target="_blank" rel="noopener noreferrer">
                          {url}
                        </a>
                      ))}
                    </div>
                  )}
                  <div className="open-answer">
                    <textarea
                      value={openAnswers[testData.questions[currentQuestion].id] || ''}
                      onChange={(e) =>
                        handleOpenAnswerChange(
                          testData.questions[currentQuestion].id,
                          e.target.value
                        )
                      }
                      placeholder="Введите ваш ответ здесь..."
                      rows={8}
                    />
                    <div className="answer-hint">
                      <span className="hint-text">Этот ответ будет проверен учителем вручную.</span>
                    </div>
                  </div>
                </div>
              ) : (
                <div className="question-card">
                  <div className="question-header">
                    <h3>Вопрос {currentQuestion + 1} (с выбором ответа)</h3>
                    <span className="question-points">
                      Баллы: {testData.questions[currentQuestion].points}
                    </span>
                  </div>
                  <div className="question-text">
                    <p>{testData.questions[currentQuestion].text}</p>
                  </div>
                  <div className="answer-options">
                    {testData.questions[currentQuestion].choices.map((choice) => (
                      <div key={choice.id} className="option-item">
                        <input
                          type="radio"
                          id={`q${testData.questions[currentQuestion].id}_ch${choice.id}`}
                          name={`question_${testData.questions[currentQuestion].id}`}
                          checked={
                            userAnswers[testData.questions[currentQuestion].id] === choice.id
                          }
                          onChange={() =>
                            handleAnswerChange(testData.questions[currentQuestion].id, choice.id)
                          }
                        />
                        <label
                          htmlFor={`q${testData.questions[currentQuestion].id}_ch${choice.id}`}
                        >
                          {choice.value}
                        </label>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              <div className="navigation-buttons">
                <button
                  className="nav-btn prev-btn"
                  onClick={() => setCurrentQuestion((p) => Math.max(0, p - 1))}
                  disabled={currentQuestion === 0}
                >
                  Предыдущий вопрос
                </button>
                <button
                  className="nav-btn next-btn"
                  onClick={() => setCurrentQuestion((p) => Math.min(totalQuestions - 1, p + 1))}
                  disabled={currentQuestion === totalQuestions - 1}
                >
                  Следующий вопрос
                </button>
              </div>
            </div>
          </div>
        </>
      ) : (
        <div className="test-results">
          <div className="results-header">
            <h2>🎉 Тест завершен!</h2>
            <p>Ваши ответы отправлены на проверку.</p>
          </div>
          <div className="results-actions">
            <button className="action-btn" onClick={() => navigate('/tests')}>
              Вернуться к списку тестов
            </button>
            <button className="action-btn primary" onClick={() => navigate('/analytics')}>
              Смотреть аналитику
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

export default TestDetails;
