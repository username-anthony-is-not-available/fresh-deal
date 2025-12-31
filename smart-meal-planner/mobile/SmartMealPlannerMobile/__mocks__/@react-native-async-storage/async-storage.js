// __mocks__/@react-native-async-storage/async-storage.js
let cache = {};
export default {
  setItem: jest.fn((key, value) => {
    return new Promise(resolve => {
      cache[key] = value;
      resolve(value);
    });
  }),
  getItem: jest.fn(key => {
    return new Promise(resolve => {
      resolve(cache[key] || null);
    });
  }),
  removeItem: jest.fn(key => {
    return new Promise(resolve => {
      delete cache[key];
      resolve();
    });
  }),
  clear: jest.fn(() => {
    return new Promise(resolve => {
      cache = {};
      resolve();
    });
  }),
  getAllKeys: jest.fn(() => {
    return new Promise(resolve => {
      resolve(Object.keys(cache));
    });
  }),
};
