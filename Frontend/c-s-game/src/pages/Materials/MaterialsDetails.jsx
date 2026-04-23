import React, { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { fetchMaterialById } from '../../api/api';
import './MaterialsDetails.css';

const MaterialDetails = () => {
  const { id } = useParams();
  const [material, setMaterial] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const loadMaterial = async () => {
      try {
        const data = await fetchMaterialById(id);
        setMaterial(data);
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };
    loadMaterial();
  }, [id]);

  const formatDate = (dateString) => {
    if (!dateString) return '';
    const date = new Date(dateString);
    return date.toLocaleDateString('ru-RU', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
    });
  };

  const renderBlocks = () => {
    if (!material.blocks || material.blocks.length === 0) {
      return <p>Содержание отсутствует</p>;
    }
    return material.blocks
      .sort((a, b) => (a.order_index || 0) - (b.order_index || 0))
      .map((block) => {
        switch (block.block_type) {
          case 'text':
            return (
              <div key={block.id} className="content-text-block">
                {block.title && <h3>{block.title}</h3>}
                <div
                  dangerouslySetInnerHTML={{ __html: block.body?.replace(/\n/g, '<br/>') || '' }}
                />
              </div>
            );
          case 'documentation_link':
            return (
              <div key={block.id} className="doc-link-block">
                <a href={block.url} target="_blank" rel="noopener noreferrer">
                  {block.title || 'Документация'}
                </a>
              </div>
            );
          case 'video_link':
            return (
              <div key={block.id} className="video-block">
                {block.title && <h4>{block.title}</h4>}
                <iframe
                  src={block.url}
                  title={block.title || 'Видео'}
                  frameBorder="0"
                  allowFullScreen
                />
              </div>
            );
          case 'code_example':
            return (
              <pre key={block.id} className="code-block">
                <code>{block.body}</code>
              </pre>
            );
          default:
            return null;
        }
      });
  };

  if (loading) return <div className="loading">Загрузка материала...</div>;
  if (error) return <div className="error">Ошибка: {error}</div>;
  if (!material) return <div className="not-found">Материал не найден</div>;

  return (
    <div className="material-details-page">
      <div className="material-details-header">
        <Link to="/materials" className="back-button">
          Назад к материалам
        </Link>
        <h1>{material.title}</h1>
        <div className="material-meta">
          {material.created_at && (
            <span className="material-date">{formatDate(material.created_at)}</span>
          )}
          {material.content_url && (
            <a
              href={material.content_url}
              target="_blank"
              rel="noopener noreferrer"
              className="doc-link-header"
            >
              Официальная документация
            </a>
          )}
        </div>
      </div>

      <div className="material-content-full">
        <div className="content-section">
          <h2>Полное содержание</h2>
          <div className="content-text">{renderBlocks()}</div>
        </div>

        <div className="material-sidebar">
          <div className="sidebar-section">
            <h3>Связанные тесты</h3>
            <div className="tests-list">
              {material.tests && material.tests.length > 0 ? (
                material.tests.map((test) => (
                  <div key={test.id} className="test-item">
                    <span className="test-bullet">•</span>
                    <span className="test-name">{test.title}</span>
                    <Link to={`/tests/${test.id}`} className="take-test-link">
                      Пройти тест
                    </Link>
                  </div>
                ))
              ) : (
                <p>Нет связанных тестов</p>
              )}
            </div>
          </div>

          <div className="sidebar-section">
            <h3>Информация о материале</h3>
            <div className="material-info">
              <div className="info-item">
                <span className="info-label">ID материала:</span>
                <span className="info-value">#{material.id}</span>
              </div>
              {material.created_at && (
                <div className="info-item">
                  <span className="info-label">Дата публикации:</span>
                  <span className="info-value">{formatDate(material.created_at)}</span>
                </div>
              )}
              <div className="info-item">
                <span className="info-label">Кол-во тестов:</span>
                <span className="info-value">{material.tests?.length || 0}</span>
              </div>
              <div className="info-item">
                <span className="info-label">Документация:</span>
                <span className="info-value">
                  {material.content_url ? 'Доступна' : 'Не доступна'}
                </span>
              </div>
              <button className="action-btn save-btn save-btn-sidebar">
                Сохранить для изучения
              </button>
            </div>
          </div>

          {material.content_url && (
            <div className="sidebar-section">
              <h3>Полезные ссылки</h3>
              <a
                href={material.content_url}
                target="_blank"
                rel="noopener noreferrer"
                className="external-link"
              >
                Открыть документацию
              </a>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default MaterialDetails;
