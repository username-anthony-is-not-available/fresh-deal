/* eslint-disable no-undef */
// jest.setup.js
import 'react-native-gesture-handler/jestSetup';

jest.mock('react-native/Libraries/EventEmitter/NativeEventEmitter');

jest.mock('react-native/Libraries/Interaction/InteractionManager', () => ({
  ...jest.requireActual(
    'react-native/Libraries/Interaction/InteractionManager',
  ),
  runAfterInteractions: jest.fn(cb => cb()),
  createInteractionHandle: jest.fn(() => 1),
  clearInteractionHandle: jest.fn(),
}));

jest.mock('react-native/Libraries/Components/Keyboard/Keyboard', () => ({
  addListener: jest.fn(() => ({
    remove: jest.fn(),
  })),
  removeListener: jest.fn(),
  removeAllListeners: jest.fn(),
  dismiss: jest.fn(),
}));

jest.mock('react-native-safe-area-context', () => {
  const inset = {top: 0, right: 0, bottom: 0, left: 0};
  return {
    ...jest.requireActual('react-native-safe-area-context'),
    SafeAreaProvider: jest.fn(({children}) => children),
    SafeAreaConsumer: jest.fn(({children}) => children(inset)),
    useSafeAreaInsets: jest.fn(() => inset),
  };
});
