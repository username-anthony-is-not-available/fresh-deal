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
import {useTheme} from '../context/ThemeContext';

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
  const [lastUpdated, setLastUpdated] = useState<number | null>(null);
  const [isOffline, setIsOffline] = useState(false);
  const {user} = useAuth();
  const {colors} = useTheme();

  const fetchShoppingList = useCallback(async () => {
    if (!user) {
      setError('You must be logged in to see your shopping list.');
      setLoading(false);
      return;
    }
    try {
      setError(null);
      const result = await getShoppingList(user.id);
      setShoppingList(result.data?.min_cost_stores || null);
      setLastUpdated(result.timestamp);
      setIsOffline(result.isOffline);
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
      <View style={[styles.centered, {backgroundColor: colors.background}]}>
        <ActivityIndicator size="large" color={colors.primary} />
      </View>
    );
  }

  if (error && !shoppingList) {
    return (
      <View style={[styles.centered, {backgroundColor: colors.background}]}>
        <Text style={[styles.errorText, {color: colors.error}]}>{error}</Text>
      </View>
    );
  }

  if (!shoppingList) {
    return (
      <View style={[styles.centered, {backgroundColor: colors.background}]}>
        <Text style={{color: colors.text}}>No shopping list found. Generate a meal plan first!</Text>
      </View>
    );
  }

  return (
    <SafeAreaView style={[styles.container, {backgroundColor: colors.background}]}>
      {isOffline && (
        <View style={[styles.offlineBanner, {backgroundColor: colors.accent}]}>
          <Text style={styles.offlineText}>Viewing offline version</Text>
        </View>
      )}
      <ScrollView
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={colors.primary} />
        }>
        <View style={[styles.headerContainer, {backgroundColor: colors.surface}]}>
          <Text style={[styles.header, {color: colors.text}]}>Your Shopping List</Text>
          {lastUpdated && (
            <Text style={[styles.lastUpdatedText, {color: colors.textSecondary}]}>
              Last updated: {new Date(lastUpdated).toLocaleString()}
            </Text>
          )}
        </View>
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
  },
  centered: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    padding: 20,
  },
  errorText: {
    textAlign: 'center',
  },
  headerContainer: {
    paddingBottom: 8,
  },
  header: {
    fontSize: 24,
    fontWeight: 'bold',
    padding: 16,
    paddingBottom: 4,
  },
  lastUpdatedText: {
    fontSize: 12,
    paddingHorizontal: 16,
    paddingBottom: 8,
  },
  offlineBanner: {
    padding: 8,
    alignItems: 'center',
  },
  offlineText: {
    color: '#000',
    fontWeight: 'bold',
  },
});

export default ShoppingListScreen;
