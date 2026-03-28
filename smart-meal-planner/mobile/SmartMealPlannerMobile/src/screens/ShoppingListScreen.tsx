// src/screens/ShoppingListScreen.tsx
import React, {useEffect, useState, useCallback} from 'react';
import {
  View,
  Text,
  ScrollView,
  ActivityIndicator,
  StyleSheet,
  SafeAreaView,
  RefreshControl,
} from 'react-native';
import AsyncStorage from '@react-native-async-storage/async-storage';
import {getShoppingList} from '../services/api';
import StoreCard from '../components/StoreCard';
import IngredientItem from '../components/IngredientItem';
import {useAuth} from '../context/AuthContext';

// Define types for the shopping list data based on backend response
interface Item {
  name: string;
  qty: number;
  unit: string;
  price_per_unit: number;
  cost: number;
  discount_pct?: number;
  category: string;
}

interface RecommendedStore {
  store: string;
  store_id: number;
  chain: string;
  items: Item[];
  subtotal: number;
  savings: number;
}

interface ShoppingListResponse {
  strategy: string;
  recommended_stores: RecommendedStore[];
  total_cost: number;
  total_savings: number;
  total_regular_cost: number;
  unmatched_items: string[];
}

const CACHE_KEY = 'cached_shopping_list';
const TIMESTAMP_KEY = 'shopping_list_timestamp';

const ShoppingListScreen = () => {
  const [shoppingData, setShoppingData] = useState<ShoppingListResponse | null>(null);
  const [lastUpdated, setLastUpdated] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const {user} = useAuth();

  const loadCache = useCallback(async () => {
    try {
      const cachedData = await AsyncStorage.getItem(CACHE_KEY);
      const timestamp = await AsyncStorage.getItem(TIMESTAMP_KEY);
      if (cachedData) {
        setShoppingData(JSON.parse(cachedData));
        setLastUpdated(timestamp);
      }
    } catch (e) {
      console.error('Failed to load shopping list cache', e);
    }
  }, []);

  const fetchShoppingList = useCallback(async (showLoading = true) => {
    if (!user) {
      setError('You must be logged in to see your shopping list.');
      setLoading(false);
      return;
    }
    if (showLoading) {setLoading(true);}
    try {
      setError(null);
      const data: ShoppingListResponse = await getShoppingList(user.id);
      if (data && data.recommended_stores) {
        setShoppingData(data);
        const now = new Date().toLocaleString();
        setLastUpdated(now);
        await AsyncStorage.setItem(CACHE_KEY, JSON.stringify(data));
        await AsyncStorage.setItem(TIMESTAMP_KEY, now);
      } else {
        setShoppingData(null);
      }
    } catch (e) {
      setError('Failed to load shopping list. Showing cached data if available.');
      console.error(e);
      await loadCache();
    } finally {
      setLoading(false);
    }
  }, [user, loadCache]);

  useEffect(() => {
    const init = async () => {
      await loadCache();
      fetchShoppingList(false);
    };
    init();
  }, [fetchShoppingList, loadCache]);

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    await fetchShoppingList(false);
    setRefreshing(false);
  }, [fetchShoppingList]);

  if (loading && !shoppingData) {
    return (
      <View style={styles.centered}>
        <ActivityIndicator size="large" />
      </View>
    );
  }

  if (error && !shoppingData) {
    return (
      <View style={styles.centered}>
        <Text style={styles.errorText}>{error}</Text>
      </View>
    );
  }

  if (!shoppingData || !shoppingData.recommended_stores || shoppingData.recommended_stores.length === 0) {
    return (
      <View style={styles.centered}>
        <Text>No shopping list found. Generate a meal plan first!</Text>
      </View>
    );
  }

  return (
    <SafeAreaView style={styles.container}>
      <ScrollView
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} />
        }>
        <View style={styles.headerContainer}>
          <Text style={styles.header}>Your Shopping List</Text>
          {lastUpdated && (
            <Text style={styles.timestamp}>Last updated: {lastUpdated}</Text>
          )}
          <Text style={styles.summaryText}>
            Estimated total: ${shoppingData.total_cost.toFixed(2)} (Saved ${shoppingData.total_savings.toFixed(2)})
          </Text>
        </View>

        {shoppingData.recommended_stores.map((storeData) => (
          <StoreCard
            key={storeData.store_id}
            storeName={storeData.store}
            totalCost={storeData.subtotal}>
            {storeData.items.map((item, index) => (
              <IngredientItem
                key={`${item.name}-${index}`}
                name={item.name}
                quantity={item.qty}
                unit={item.unit}
                price={item.cost}
              />
            ))}
          </StoreCard>
        ))}

        {shoppingData.unmatched_items && shoppingData.unmatched_items.length > 0 && (
          <View style={styles.unmatchedSection}>
            <Text style={styles.unmatchedHeader}>Items not found on sale:</Text>
            {shoppingData.unmatched_items.map((item, index) => (
              <Text key={index} style={styles.unmatchedItem}>• {item}</Text>
            ))}
          </View>
        )}
      </ScrollView>
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#f5f5f5',
  },
  centered: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    padding: 20,
  },
  errorText: {
    color: 'red',
    textAlign: 'center',
    marginBottom: 10,
  },
  headerContainer: {
    backgroundColor: 'white',
    padding: 16,
    borderBottomWidth: 1,
    borderBottomColor: '#eee',
  },
  header: {
    fontSize: 24,
    fontWeight: 'bold',
  },
  timestamp: {
    fontSize: 12,
    color: '#666',
    marginTop: 4,
  },
  summaryText: {
    fontSize: 14,
    color: '#333',
    marginTop: 8,
    fontWeight: '500',
  },
  unmatchedSection: {
    padding: 16,
    backgroundColor: 'white',
    marginVertical: 16,
    marginHorizontal: 16,
    borderRadius: 8,
  },
  unmatchedHeader: {
    fontSize: 16,
    fontWeight: 'bold',
    marginBottom: 8,
    color: '#666',
  },
  unmatchedItem: {
    fontSize: 14,
    color: '#333',
    paddingVertical: 2,
  },
});

export default ShoppingListScreen;
