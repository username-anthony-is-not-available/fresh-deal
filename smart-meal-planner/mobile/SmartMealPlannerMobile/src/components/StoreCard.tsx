// src/components/StoreCard.tsx
import React from 'react';
import {View, Text, StyleSheet} from 'react-native';
import {useTheme} from '../context/ThemeContext';

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
  const {colors} = useTheme();

  return (
    <View style={[styles.card, {backgroundColor: colors.surface, borderColor: colors.border}]}>
      <Text style={[styles.storeName, {color: colors.text}]}>
        {storeName} - ${totalCost.toFixed(2)}
      </Text>
      <View style={styles.itemList}>{children}</View>
    </View>
  );
};

const styles = StyleSheet.create({
  card: {
    borderRadius: 8,
    padding: 16,
    marginVertical: 8,
    marginHorizontal: 16,
    borderWidth: 1,
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
