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
import {getShoppingList} from '../services/api';
import StoreCard from '../components/StoreCard';
import IngredientItem from '../components/IngredientItem';
import {useAuth} from '../context/AuthContext';

// Define types for the shopping list data
interface ShoppingItem {
  product_name: string;
  quantity: number;
  unit: string;
  price: number;
}

interface StoreData {
  items: ShoppingItem[];
  total_cost: number;
}

interface ShoppingListData {
  [storeName: string]: StoreData;
}

const ShoppingListScreen = () => {
  const [shoppingList, setShoppingList] = useState<ShoppingListData | null>(
    null,
  );
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const {user} = useAuth();

  const fetchShoppingList = useCallback(async () => {
    if (!user) {
      setError('You must be logged in to see your shopping list.');
      setLoading(false);
      return;
    }
    try {
      setError(null);
      const data = await getShoppingList(user.id);
      setShoppingList(data.min_cost_stores || null);
    } catch (e) {
      setError('Failed to load shopping list. Please try again later.');
      console.error(e);
    } finally {
      setLoading(false);
    }
  }, [user]);

  useEffect(() => {
    setLoading(true);
    fetchShoppingList();
  }, [fetchShoppingList]);

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    await fetchShoppingList();
    setRefreshing(false);
  }, [fetchShoppingList]);

  if (loading) {
    return (
      <View style={styles.centered}>
        <ActivityIndicator size="large" />
      </View>
    );
  }

  if (error && !shoppingList) {
    return (
      <View style={styles.centered}>
        <Text style={styles.errorText}>{error}</Text>
      </View>
    );
  }

  if (!shoppingList) {
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
        <Text style={styles.header}>Your Shopping List</Text>
        {Object.entries(shoppingList).map(([storeName, storeData]) => (
          <StoreCard
            key={storeName}
            storeName={storeName}
            totalCost={storeData.total_cost}>
            {storeData.items.map(item => (
              <IngredientItem
                key={item.product_name}
                name={item.product_name}
                quantity={item.quantity}
                unit={item.unit}
                price={item.price}
              />
            ))}
          </StoreCard>
        ))}
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
  },
  header: {
    fontSize: 24,
    fontWeight: 'bold',
    padding: 16,
    backgroundColor: 'white',
  },
});

export default ShoppingListScreen;
