import React from 'react';
import { Link } from 'react-router-dom';
import { useMaterials } from '../../hooks/useMaterials';
import './Materials.css';

const Materials = () => {
  const { data: materials, isLoading, error } = useMaterials();

  if (isLoading) return <div className="loading">Загрузка материалов...</div>;
  if (error) return <div className="error">Ошибка: {error.message}</div>;

  const formatDate = (dateString) => {
    if (!dateString) return '';
    return new Date(dateString).toLocaleDateString('ru-RU', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
    });
  };

  return (
    <div className="materials-page">
      <div className="materials-header">
        <h1>Учебные материалы</h1>
        <p className="materials-subtitle">Изучайте материалы и закрепляйте знания на практике</p>
      </div>

      <div className="materials-grid">
        {materials.map((material) => (
          <div key={material.id} className="material-card">
            <div className="material-header">
              <Link to={`/materials/${material.id}`} className="material-title-link">
                <h3 className="material-title">{material.title}</h3>
              </Link>
              {material.created_at && (
                <span className="material-date">{formatDate(material.created_at)}</span>
              )}
            </div>
            <div className="material-content">
              <p>{material.description || material.content_text?.slice(0, 200) + '...'}</p>
            </div>
            <div className="material-footer">
              <div className="material-links">
                {material.content_url && (
                  <a
                    href={material.content_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="doc-link"
                  >
                    Документация
                  </a>
                )}
                {material.tests?.length > 0 && (
                  <div className="tests-section">
                    <h4>Связанные тесты:</h4>
                    <div className="tests-list">
                      {material.tests.map((test) => (
                        <Link key={test.id} to={`/tests/${test.id}`} className="test-link">
                          {test.title}
                        </Link>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>
        ))}
      </div>

      <div className="materials-stats">
        <div className="stat-item">
          <div className="stat-number">{materials.length}</div>
          <div className="stat-label">Всего материалов</div>
        </div>
        <div className="stat-item">
          <div className="stat-number">
            {materials.reduce((acc, m) => acc + (m.tests?.length || 0), 0)}
          </div>
          <div className="stat-label">Всего тестов</div>
        </div>
        <div className="stat-item">
          <div className="stat-number">{materials.filter((m) => m.content_url).length}</div>
          <div className="stat-label">С документацией</div>
        </div>
      </div>
    </div>
  );
};

export default Materials;
