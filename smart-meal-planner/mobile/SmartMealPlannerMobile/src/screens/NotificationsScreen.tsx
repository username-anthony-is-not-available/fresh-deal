// src/screens/NotificationsScreen.tsx
import React from 'react';
import {View, Text, StyleSheet, FlatList, SafeAreaView} from 'react-native';

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

const NotificationItem = ({item}: {item: Notification}) => (
  <View style={styles.itemContainer}>
    <Text style={styles.itemTitle}>{item.title}</Text>
    <Text style={styles.itemMessage}>{item.message}</Text>
    <Text style={styles.itemTimestamp}>{item.timestamp}</Text>
  </View>
);

const NotificationsScreen = () => {
  return (
    <SafeAreaView style={styles.container}>
      <FlatList
        data={MOCK_NOTIFICATIONS}
        renderItem={({item}) => <NotificationItem item={item} />}
        keyExtractor={item => item.id}
        ListHeaderComponent={
          <Text style={styles.header}>Notifications</Text>
        }
      />
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#f5f5f5',
  },
  header: {
    fontSize: 24,
    fontWeight: 'bold',
    padding: 16,
    backgroundColor: 'white',
  },
  itemContainer: {
    backgroundColor: 'white',
    padding: 16,
    borderBottomWidth: 1,
    borderBottomColor: '#eee',
  },
  itemTitle: {
    fontSize: 16,
    fontWeight: 'bold',
  },
  itemMessage: {
    fontSize: 14,
    color: '#333',
    marginTop: 4,
  },
  itemTimestamp: {
    fontSize: 12,
    color: '#999',
    marginTop: 8,
    textAlign: 'right',
  },
});

export default NotificationsScreen;
