import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import './Materials.css';

const Materials = () => {
  const [materials] = useState([
    {
      id: 1,
      title: 'Введение в React.js',
      description:
        'React - это JavaScript-библиотека для создания пользовательских интерфейсов. Она позволяет создавать сложные UI из небольших и изолированных частей кода, называемых «компонентами». В этом материале рассматриваются основные концепции React.',
      docLink: 'https://reactjs.org/docs/getting-started.html',
      publicationDate: '2024-01-15',
      relatedTests: [
        { id: 1, name: 'Основы React.js' },
        { id: 2, name: 'Компоненты и пропсы' },
        { id: 3, name: 'Состояние и жизненный цикл' },
      ],
    },
    {
      id: 2,
      title: 'JavaScript: современные возможности ES6+',
      description:
        'ES6 (ECMAScript 2015) принес множество новых возможностей в JavaScript. Рассмотрим ключевые нововведения: стрелочные функции, деструктуризация, операторы spread/rest, классы, промисы, async/await, модули и многое другое.',
      docLink: 'https://developer.mozilla.org/ru/docs/Web/JavaScript',
      publicationDate: '2024-01-20',
      relatedTests: [
        { id: 5, name: 'ES6+ Syntax' },
        { id: 6, name: 'Асинхронный JavaScript' },
        { id: 7, name: 'Классы и наследование' },
      ],
    },
    {
      id: 3,
      title: 'Основы CSS Grid и Flexbox',
      description:
        'CSS Grid и Flexbox – современные технологии верстки, которые решают задачи создания адаптивных макетов. Материал содержит примеры и сравнение подходов.',
      docLink: null,
      publicationDate: '2024-02-01',
      relatedTests: [
        { id: 8, name: 'CSS Layout' },
        { id: 9, name: 'Адаптивная верстка' },
      ],
    },
    {
      id: 4,
      title: 'Основы Node.js и Express',
      description:
        'Node.js – среда выполнения JavaScript на стороне сервера, Express – минималистичный веб-фреймворк. В материале рассматривается создание простого сервера, маршрутизация, middleware и работа с базами данных.',
      docLink: 'https://nodejs.org/docs/latest/api/',
      publicationDate: '2024-02-10',
      relatedTests: [
        { id: 11, name: 'Node.js основы' },
        { id: 12, name: 'REST API с Express' },
      ],
    },
  ]);

  const formatDate = (dateString) => {
    const date = new Date(dateString);
    return date.toLocaleDateString('ru-RU', {
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
              <span className="material-date">{formatDate(material.publicationDate)}</span>
            </div>

            <div className="material-content">
              <p>{material.description}</p>
            </div>

            <div className="material-footer">
              <div className="material-links">
                {material.docLink && (
                  <a
                    href={material.docLink}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="doc-link"
                  >
                    Документация
                  </a>
                )}

                <div className="tests-section">
                  <h4>Связанные тесты:</h4>
                  <div className="tests-list">
                    {material.relatedTests.map((test) => (
                      <Link key={test.id} to={`/tests/${test.id}`} className="test-link">
                        {test.name}
                      </Link>
                    ))}
                  </div>
                </div>
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
            {materials.reduce((acc, m) => acc + m.relatedTests.length, 0)}
          </div>
          <div className="stat-label">Всего тестов</div>
        </div>
        <div className="stat-item">
          <div className="stat-number">{materials.filter((m) => m.docLink).length}</div>
          <div className="stat-label">С документацией</div>
        </div>
      </div>
    </div>
  );
};

export default Materials;
