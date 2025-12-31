// __mocks__/jwt-decode.js
export const jwtDecode = jest.fn(token => {
  if (typeof token !== 'string') {
    throw new Error('Invalid token specified');
  }
  // Return a mock decoded token for testing purposes
  return {
    sub: '1',
    name: 'Test User',
    iat: Date.now() / 1000,
    exp: Date.now() / 1000 + 3600, // Expires in 1 hour
  };
});
