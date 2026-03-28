// src/screens/NotificationsScreen.tsx
import React from 'react';
import {View, Text, StyleSheet, FlatList, SafeAreaView} from 'react-native';
import {useTheme} from '../context/ThemeContext';

interface Notification {
  id: string;
  title: string;
  message: string;
  timestamp: string;
}

const MOCK_NOTIFICATIONS: Notification[] = [
  {
    id: '1',
    title: 'Meal Plan Ready!',
    message: 'Your new weekly meal plan has been generated.',
    timestamp: '10 minutes ago',
  },
  {
    id: '2',
    title: 'Shopping List Updated',
    message: 'Your shopping list is updated based on your new meal plan.',
    timestamp: '8 minutes ago',
  },
  {
    id: '3',
    title: 'Deal Alert!',
    message: 'Avocados are on sale at your favorite store.',
    timestamp: '2 hours ago',
  },
  {
    id: '4',
    title: 'Dinner Time',
    message: "Don't forget to prepare your delicious salmon dinner tonight.",
    timestamp: 'yesterday',
  },
];

const NotificationItem = ({item}: {item: Notification}) => {
  const {colors} = useTheme();
  return (
    <View style={[styles.itemContainer, {backgroundColor: colors.surface, borderBottomColor: colors.border}]}>
      <Text style={[styles.itemTitle, {color: colors.text}]}>{item.title}</Text>
      <Text style={[styles.itemMessage, {color: colors.textSecondary}]}>{item.message}</Text>
      <Text style={[styles.itemTimestamp, {color: colors.textSecondary}]}>{item.timestamp}</Text>
    </View>
  );
};

const NotificationsScreen = () => {
  const {colors} = useTheme();
  return (
    <SafeAreaView style={[styles.container, {backgroundColor: colors.background}]}>
      <FlatList
        data={MOCK_NOTIFICATIONS}
        renderItem={({item}) => <NotificationItem item={item} />}
        keyExtractor={item => item.id}
        ListHeaderComponent={
          <View style={{backgroundColor: colors.surface}}>
            <Text style={[styles.header, {color: colors.text}]}>Notifications</Text>
          </View>
        }
      />
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  header: {
    fontSize: 24,
    fontWeight: 'bold',
    padding: 16,
  },
  itemContainer: {
    padding: 16,
    borderBottomWidth: 1,
  },
  itemTitle: {
    fontSize: 16,
    fontWeight: 'bold',
  },
  itemMessage: {
    fontSize: 14,
    marginTop: 4,
  },
  itemTimestamp: {
    fontSize: 12,
    marginTop: 8,
    textAlign: 'right',
  },
});

export default NotificationsScreen;
