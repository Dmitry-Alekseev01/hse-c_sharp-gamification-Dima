const API_BASE_URL = '/api/v1';

export const setToken = (token) => {
  localStorage.setItem('access_token', token);
  localStorage.setItem('isAuthenticated', 'true');
};

export const getToken = () => localStorage.getItem('access_token');

export const removeToken = () => {
  localStorage.removeItem('access_token');
  localStorage.removeItem('isAuthenticated');
  localStorage.removeItem('userEmail');
  localStorage.removeItem('userName');
};

async function authFetch(url, options = {}) {
  const token = getToken();
  const headers = {
    'Content-Type': 'application/json',
    ...(token && { Authorization: `Bearer ${token}` }),
    ...options.headers,
  };
  const response = await fetch(`${API_BASE_URL}${url}`, { ...options, headers });
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail || `Ошибка ${response.status}`);
  }
  return response.json();
}

export const fetchUserProfile = async () => {
  const profile = await authFetch('/auth/me');
  if (profile?.username) localStorage.setItem('userEmail', profile.username);
  if (profile?.full_name) localStorage.setItem('userName', profile.full_name);
  return profile;
};

export const loginUser = async (username, password) => {
  const response = await fetch(`${API_BASE_URL}/auth/token`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: new URLSearchParams({ username, password }).toString(),
  });
  if (!response.ok) throw new Error('Неверные учетные данные');
  const data = await response.json();
  setToken(data.access_token);
  localStorage.setItem('userEmail', username);
  try {
    await fetchUserProfile();
  } catch (_) {}
  return data;
};

export const registerUser = async (username, password, fullName) => {
  const response = await fetch(`${API_BASE_URL}/auth/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password, full_name: fullName }),
  });
  if (!response.ok) throw new Error('Ошибка регистрации');
  await response.json();
  return loginUser(username, password);
};

export const logoutUser = () => {
  removeToken();
  window.location.href = '/';
};

function adaptMaterial(apiMaterial) {
  let content_text = '';
  let content_url = null;
  if (apiMaterial.blocks) {
    const textBlock = apiMaterial.blocks.find((b) => b.block_type === 'text');
    if (textBlock?.body) content_text = textBlock.body;
    const docBlock = apiMaterial.blocks.find((b) => b.block_type === 'documentation_link');
    if (docBlock?.url) content_url = docBlock.url;
  }
  if (!content_text && apiMaterial.content_text) content_text = apiMaterial.content_text;
  if (!content_url && apiMaterial.content_url) content_url = apiMaterial.content_url;
  const tests = (apiMaterial.related_test_ids || []).map((id) => ({ id, title: `Тест #${id}` }));
  return {
    id: apiMaterial.id,
    title: apiMaterial.title,
    description: apiMaterial.description || '',
    content_text,
    content_url,
    created_at: apiMaterial.published_at,
    tests,
  };
}

export const fetchMaterials = async () => {
  const data = await authFetch('/materials/');
  return data.map(adaptMaterial);
};

export const fetchMaterialById = async (id) => {
  const data = await authFetch(`/materials/${id}/`);
  return adaptMaterial(data);
};

export const fetchTests = async () => {
  return authFetch('/tests/');
};

export const fetchTestContent = async (testId) => {
  return authFetch(`/tests/${testId}/content/`);
};

export const startTestAttempt = async (testId) => {
  return authFetch(`/tests/${testId}/attempts/start/`, { method: 'POST' });
};

export const submitAnswer = async (testId, questionId, answerPayload, attemptId = null) => {
  const body = { test_id: testId, question_id: questionId, answer_payload: answerPayload };
  if (attemptId) body.attempt_id = attemptId;
  return authFetch('/answers/', { method: 'POST', body: JSON.stringify(body) });
};

export const completeTestAttempt = async (attemptId) => {
  return authFetch(`/tests/attempts/${attemptId}/complete/`, { method: 'POST' });
};

export const fetchUserAnswers = async (testId) => {
  return authFetch(`/answers/test/${testId}/`);
};

export const fetchUserProgress = async (userId) => {
  return authFetch(`/analytics/user/${userId}/progress/`);
};

export const fetchLeaderboard = async () => {
  return authFetch('/analytics/leaderboard/');
};

export const fetchOverview = async () => {
  return authFetch('/analytics/overview/');
};

export const fetchTestCompletedSummary = async (testId) => {
  return authFetch(`/analytics/test/${testId}/completed-summary/`);
};

export const fetchLevels = async () => {
  return authFetch('/levels/');
};

export const updateUserProfile = async (fullName) => {
  return authFetch('/users/me', {
    method: 'PATCH',
    body: JSON.stringify({ full_name: fullName }),
  });
};
