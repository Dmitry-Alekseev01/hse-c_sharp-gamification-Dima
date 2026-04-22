import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { fetchUserProfile, updateUserProfile, getToken } from '../../api/api';
import { PERSONAL_ACCOUNT_ROUTE } from '../../routing/const';
import './EditProfile.css';

const EditProfile = () => {
  const navigate = useNavigate();
  const [name, setName] = useState('');
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    const loadProfile = async () => {
      if (!getToken()) {
        navigate(PERSONAL_ACCOUNT_ROUTE);
        return;
      }
      try {
        const profile = await fetchUserProfile();
        setName(profile.full_name || '');
      } catch (err) {
        setError(err.message);
      }
    };
    loadProfile();
  }, [navigate]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!name.trim()) {
      setError('Имя не может быть пустым');
      return;
    }
    setIsSaving(true);
    setError('');
    try {
      const updated = await updateUserProfile(name);
      localStorage.setItem('userName', updated.full_name);
      navigate(PERSONAL_ACCOUNT_ROUTE);
    } catch (err) {
      setError(err.message);
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="edit-profile-container">
      <div className="edit-profile-card">
        <h1>Редактирование профиля</h1>
        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label htmlFor="name">Имя</label>
            <input
              type="text"
              id="name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Введите ваше имя"
              required
            />
          </div>
          {error && <div className="error-message">{error}</div>}
          <div className="form-actions">
            <button type="submit" className="save-btn" disabled={isSaving}>
              {isSaving ? 'Сохранение...' : 'Сохранить'}
            </button>
            <button
              type="button"
              className="cancel-btn"
              onClick={() => navigate(PERSONAL_ACCOUNT_ROUTE)}
            >
              Отмена
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default EditProfile;
