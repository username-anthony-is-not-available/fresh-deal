// src/components/StoreCard.tsx
import React from 'react';
import {View, Text, StyleSheet} from 'react-native';

interface StoreCardProps {
  storeName: string;
  totalCost: number;
  children: React.ReactNode;
}

const StoreCard: React.FC<StoreCardProps> = ({
  storeName,
  totalCost,
  children,
}) => {
  return (
    <View style={styles.card}>
      <Text style={styles.storeName}>
        {storeName} - ${totalCost.toFixed(2)}
      </Text>
      <View style={styles.itemList}>{children}</View>
    </View>
  );
};

const styles = StyleSheet.create({
  card: {
    backgroundColor: '#f9f9f9',
    borderRadius: 8,
    padding: 16,
    marginVertical: 8,
    marginHorizontal: 16,
  },
  storeName: {
    fontSize: 18,
    fontWeight: 'bold',
    marginBottom: 12,
  },
  itemList: {
    paddingLeft: 8,
  },
});

export default StoreCard;
