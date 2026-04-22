export const isAuthenticated = () => {
  return (
    localStorage.getItem('isAuthenticated') === 'true' ||
    Boolean(localStorage.getItem('access_token'))
  );
};

export const login = (email, rememberMe = false) => {
  localStorage.setItem('access_token', 'local-session');
  localStorage.setItem('isAuthenticated', 'true');
  localStorage.setItem('userEmail', email);
  if (rememberMe) {
    localStorage.setItem('rememberMe', 'true');
  }
};

export const logout = () => {
  localStorage.removeItem('access_token');
  localStorage.removeItem('isAuthenticated');
  localStorage.removeItem('userEmail');
  localStorage.removeItem('userName');
  localStorage.removeItem('rememberMe');
  window.location.href = '/';
};

export const getUser = () => {
  return {
    email: localStorage.getItem('userEmail'),
    name: localStorage.getItem('userName'),
    isAuthenticated: isAuthenticated(),
  };
};
