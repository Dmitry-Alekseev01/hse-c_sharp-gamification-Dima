export const isAuthenticated = () => {
  return localStorage.getItem('isAuthenticated') === 'true';
};

export const login = (email, rememberMe = false) => {
  localStorage.setItem('isAuthenticated', 'true');
  localStorage.setItem('userEmail', email);
  if (rememberMe) {
    localStorage.setItem('rememberMe', 'true');
  }
};

export const logout = () => {
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
