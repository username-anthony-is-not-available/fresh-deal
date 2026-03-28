// src/components/MealCard.tsx
import React from 'react';
import {View, Text, StyleSheet} from 'react-native';

interface Meal {
  name: string;
  recipe: string;
}

interface MealCardProps {
  day: string;
  mealType: 'Breakfast' | 'Lunch' | 'Dinner';
  meal: Meal;
}

const MealCard: React.FC<MealCardProps> = ({day, mealType, meal}) => {
  if (!meal) {
    return null;
  }

  return (
    <View style={styles.card}>
      <Text style={styles.day}>{day}</Text>
      <Text style={styles.mealType}>{mealType}</Text>
      <Text style={styles.mealName}>{meal.name}</Text>
    </View>
  );
};

const styles = StyleSheet.create({
  card: {
    backgroundColor: 'white',
    borderRadius: 8,
    padding: 16,
    marginVertical: 8,
    marginHorizontal: 16,
    shadowColor: '#000',
    shadowOffset: {width: 0, height: 2},
    shadowOpacity: 0.1,
    shadowRadius: 4,
    elevation: 3,
  },
  day: {
    fontSize: 18,
    fontWeight: 'bold',
    marginBottom: 4,
  },
  mealType: {
    fontSize: 16,
    color: '#666',
    marginBottom: 8,
  },
  mealName: {
    fontSize: 16,
  },
});

export default MealCard;
