// src/components/IngredientItem.tsx
import React from 'react';
import {View, Text, StyleSheet} from 'react-native';

interface IngredientItemProps {
  name: string;
  quantity: number;
  unit: string;
  price: number;
}

const IngredientItem: React.FC<IngredientItemProps> = ({
  name,
  quantity,
  unit,
  price,
}) => {
  return (
    <View style={styles.container}>
      <Text style={styles.name}>{`${name} (${quantity} ${unit})`}</Text>
      <Text style={styles.price}>${price.toFixed(2)}</Text>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingVertical: 8,
    borderBottomWidth: 1,
    borderBottomColor: '#eee',
  },
  name: {
    fontSize: 16,
  },
  price: {
    fontSize: 16,
    fontWeight: '500',
  },
});

export default IngredientItem;
