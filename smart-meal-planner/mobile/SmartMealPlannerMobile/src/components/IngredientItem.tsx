// src/components/IngredientItem.tsx
import React from 'react';
import {View, Text, StyleSheet} from 'react-native';
import {useTheme} from '../context/ThemeContext';

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
  const {colors} = useTheme();

  return (
    <View style={[styles.container, {borderBottomColor: colors.border}]}>
      <Text style={[styles.name, {color: colors.text}]}>{`${name} (${quantity} ${unit})`}</Text>
      <Text style={[styles.price, {color: colors.text}]}>${price.toFixed(2)}</Text>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingVertical: 8,
    borderBottomWidth: 1,
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
