import {getLatestMealPlan} from '../api';
import apiClient from '../apiClient';
import AsyncStorage from '@react-native-async-storage/async-storage';

jest.mock('../apiClient');
const mockedApiClient = apiClient as jest.Mocked<typeof apiClient>;

describe('api offline caching', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    AsyncStorage.clear();
  });

  it('should cache and return data on successful API call', async () => {
    const mockData = {content: {day1: {Breakfast: {name: 'Eggs'}}}};
    mockedApiClient.get.mockResolvedValue(mockData);

    const result = await getLatestMealPlan(1);

    expect(result.data).toEqual(mockData.content);
    expect(result.isOffline).toBe(false);
    expect(result.timestamp).toBeDefined();

    const cached = await AsyncStorage.getItem('meal_plan_1');
    expect(cached).not.toBeNull();
    expect(JSON.parse(cached!).data).toEqual(mockData.content);
  });

  it('should return cached data when API call fails', async () => {
    const cachedData = {
      data: {day1: {Breakfast: {name: 'Cached Eggs'}}},
      timestamp: 123456789,
    };
    await AsyncStorage.setItem('meal_plan_1', JSON.stringify(cachedData));

    mockedApiClient.get.mockRejectedValue(new Error('Network error'));

    const result = await getLatestMealPlan(1);

    expect(result.data).toEqual(cachedData.data);
    expect(result.isOffline).toBe(true);
    expect(result.timestamp).toBe(cachedData.timestamp);
  });

  it('should throw error if API fails and no cache exists', async () => {
    mockedApiClient.get.mockRejectedValue(new Error('Network error'));

    await expect(getLatestMealPlan(1)).rejects.toThrow('Network error');
  });
});
