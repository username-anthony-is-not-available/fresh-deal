// src/components/MealCard.tsx
import React from 'react';
import {View, Text, StyleSheet, Image} from 'react-native';

interface Meal {
  name: string;
  recipe: string;
  image?: string;
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
      <View style={styles.header}>
        <View>
          <Text style={styles.day}>{day}</Text>
          <Text style={styles.mealType}>{mealType}</Text>
        </View>
      </View>
      <View style={styles.content}>
        {meal.image && (
          <Image
            source={{uri: meal.image.startsWith('http') ? meal.image : `https://api.smartmealplanner.com${meal.image}`}}
            style={styles.image}
            resizeMode="cover"
          />
        )}
        <View style={styles.textContainer}>
          <Text style={styles.mealName}>{meal.name}</Text>
          <Text style={styles.reason} numberOfLines={3}>
            {meal.recipe}
          </Text>
        </View>
      </View>
    </View>
  );
};

const styles = StyleSheet.create({
  card: {
    backgroundColor: 'white',
    borderRadius: 12,
    marginVertical: 8,
    marginHorizontal: 16,
    shadowColor: '#000',
    shadowOffset: {width: 0, height: 2},
    shadowOpacity: 0.1,
    shadowRadius: 4,
    elevation: 3,
    overflow: 'hidden',
  },
  header: {
    padding: 12,
    borderBottomWidth: 1,
    borderBottomColor: '#f0f0f0',
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  day: {
    fontSize: 16,
    fontWeight: 'bold',
    color: '#333',
  },
  mealType: {
    fontSize: 14,
    color: '#2ecc71',
    fontWeight: '600',
  },
  content: {
    flexDirection: 'row',
    padding: 12,
  },
  image: {
    width: 80,
    height: 80,
    borderRadius: 8,
    backgroundColor: '#eee',
  },
  textContainer: {
    flex: 1,
    marginLeft: 12,
    justifyContent: 'center',
  },
  mealName: {
    fontSize: 18,
    fontWeight: '600',
    color: '#333',
    marginBottom: 4,
  },
  reason: {
    fontSize: 14,
    color: '#666',
    lineHeight: 18,
  },
});

export default MealCard;
