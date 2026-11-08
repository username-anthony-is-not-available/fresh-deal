// src/components/IngredientItem.tsx
import React from 'react';
import {TouchableOpacity, View, Text, StyleSheet} from 'react-native';
import {useTheme} from '../context/ThemeContext';

interface IngredientItemProps {
  name: string;
  quantity: number;
  unit: string;
  price: number;
  checked?: boolean;
  onToggle?: () => void;
}

const IngredientItem: React.FC<IngredientItemProps> = ({
  name,
  quantity,
  unit,
  price,
  checked = false,
  onToggle,
}) => {
  const {colors} = useTheme();

  return (
    <TouchableOpacity
      activeOpacity={0.7}
      onPress={onToggle}
      style={[
        styles.container,
        {borderBottomColor: colors.border},
        checked && styles.checkedContainer,
      ]}>
      <View style={styles.textContainer}>
        <View style={[styles.checkbox, {borderColor: colors.primary}, checked && {backgroundColor: colors.primary}]}>
          {checked && <Text style={styles.checkmark}>✓</Text>}
        </View>
        <Text
          style={[
            styles.name,
            {color: colors.text},
            checked && styles.checkedText,
          ]}>
          {`${name} (${quantity} ${unit})`}
        </Text>
      </View>
      <Text
        style={[
          styles.price,
          {color: colors.text},
          checked && styles.checkedPrice,
        ]}>
        ${price.toFixed(2)}
      </Text>
    </TouchableOpacity>
  );
};

const styles = StyleSheet.create({
  container: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: 10,
    paddingHorizontal: 4,
    borderBottomWidth: 1,
  },
  checkedContainer: {
    opacity: 0.6,
  },
  textContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    flex: 1,
    marginRight: 8,
  },
  checkbox: {
    width: 20,
    height: 20,
    borderRadius: 4,
    borderWidth: 2,
    marginRight: 10,
    justifyContent: 'center',
    alignItems: 'center',
  },
  checkmark: {
    color: '#fff',
    fontSize: 12,
    fontWeight: 'bold',
  },
  name: {
    fontSize: 15,
    flexShrink: 1,
  },
  checkedText: {
    textDecorationLine: 'line-through',
    color: '#888',
  },
  price: {
    fontSize: 15,
    fontWeight: '500',
  },
  checkedPrice: {
    textDecorationLine: 'line-through',
    color: '#888',
  },
});

export default IngredientItem;
