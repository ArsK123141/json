from flask import Flask, request, jsonify
import os
import threading
from bot import run_bot, run_async_task
import asyncio
import sqlite3
from datetime import datetime, timezone
import requests

app = Flask(__name__)

def init_users_db():
    """Инициализация базы данных пользователей"""
    try:
        conn = sqlite3.connect('users.db')
        cursor = conn.cursor()
        
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id TEXT PRIMARY KEY,
            name TEXT,
            surname TEXT,
            username TEXT,
            numofdeals INTEGER DEFAULT 0,
            wallet TEXT DEFAULT '',
            pos INTEGER DEFAULT 0,
            neg INTEGER DEFAULT 0,
            volume REAL DEFAULT 0,
            registration_date TEXT DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Error initializing database: {str(e)}")
        return False

def check_and_add_user(user_id, name, surname, username):
    """Проверяем и добавляем пользователя в базу"""
    try:
        conn = sqlite3.connect('users.db')
        cursor = conn.cursor()
        
        # Добавляем логирование входящих данных
        print(f"Adding/updating user: {user_id}, {name}, {surname}, @{username}")
        
        cursor.execute('SELECT 1 FROM users WHERE user_id = ?', (str(user_id),))
        if not cursor.fetchone():
            cursor.execute('''
            INSERT INTO users (user_id, name, surname, username, registration_date) 
            VALUES (?, ?, ?, ?, datetime('now'))
            ''', (str(user_id), name or '', surname or '', username or ''))
            print("New user added to database")
        else:
            # Обновляем username, если он изменился
            cursor.execute('''
            UPDATE users SET username = ? WHERE user_id = ? AND (username IS NULL OR username != ?)
            ''', (username or '', str(user_id), username or ''))
            if cursor.rowcount > 0:
                print("Username updated in database")
        
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Error in check_and_add_user: {str(e)}")
        return False

@app.route('/get_user_data', methods=['POST'])
def get_user_data():
    """Получаем данные пользователя"""
    user_data = request.get_json()
    if not user_data or not user_data.get('user_id'):
        return jsonify({'success': False, 'error': 'Invalid request'}), 400
    
    try:
        conn = sqlite3.connect('users.db')
        cursor = conn.cursor()
        
        cursor.execute('''
        SELECT name, surname, username, numofdeals, wallet, pos, neg, volume, 
               strftime('%Y-%m-%d %H:%M:%S', registration_date) 
        FROM users WHERE user_id = ?
        ''', (str(user_data['user_id']),))
        
        result = cursor.fetchone()
        conn.close()
        
        if result:
            return jsonify({
                'success': True,
                'data': {
                    'name': result[0],
                    'surname': result[1],
                    'username': result[2],
                    'numofdeals': result[3],
                    'wallet': result[4],
                    'pos': result[5],
                    'neg': result[6],
                    'volume': result[7],
                    'registration_date': result[8]
                }
            })
        return jsonify({'success': False, 'error': 'User not found'}), 404
        
    except Exception as e:
        print(f"Error getting user data: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/update_user_wallet', methods=['POST'])
def update_user_wallet():
    """Обновляем кошелек пользователя"""
    data = request.get_json()
    if not data or not data.get('user_id') or not data.get('wallet'):
        return jsonify({'success': False, 'error': 'Invalid request'}), 400
    
    try:
        conn = sqlite3.connect('users.db')
        cursor = conn.cursor()
        
        cursor.execute('''
        UPDATE users SET wallet = ? WHERE user_id = ?
        ''', (data['wallet'], str(data['user_id'])))
        
        conn.commit()
        conn.close()
        return jsonify({'success': True})
        
    except Exception as e:
        print(f"Error updating wallet: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/get_registration_date', methods=['POST'])
def get_registration_date():
    """Получаем дату регистрации пользователя"""
    data = request.get_json()
    if not data or not data.get('user_id'):
        return jsonify({'success': False, 'error': 'Invalid request'}), 400
    
    try:
        conn = sqlite3.connect('users.db')
        cursor = conn.cursor()
        
        cursor.execute('''
        SELECT strftime('%Y-%m-%d %H:%M:%S', registration_date) 
        FROM users WHERE user_id = ?
        ''', (str(data['user_id']),))
        
        result = cursor.fetchone()
        conn.close()
        
        if result and result[0]:
            return jsonify({
                'success': True,
                'registration_date': result[0]
            })
        return jsonify({'success': False, 'error': 'User not found'}), 404
        
    except Exception as e:
        print(f"Error getting registration date: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/get_user_stats', methods=['POST'])
def get_user_stats():
    """Получаем статистику пользователя"""
    data = request.get_json()
    if not data or not data.get('user_id'):
        return jsonify({'success': False, 'error': 'Invalid request'}), 400
    
    try:
        conn = sqlite3.connect('users.db')
        cursor = conn.cursor()
        
        cursor.execute('''
        SELECT numofdeals, pos, neg, volume FROM users WHERE user_id = ?
        ''', (str(data['user_id']),))
        
        result = cursor.fetchone()
        conn.close()
        
        if result:
            return jsonify({
                'success': True,
                'stats': {
                    'deals': result[0],
                    'positive': result[1],
                    'negative': result[2],
                    'volume': result[3]
                }
            })
        return jsonify({'success': False, 'error': 'User not found'}), 404
        
    except Exception as e:
        print(f"Error getting user stats: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/get_active_ads', methods=['GET'])
def get_active_ads():
    
    try:

        # Получаем параметры фильтрации из запроса
        collection_filter = request.args.get('collection')
        model_filter = request.args.get('model')
        
        # Connect to database
        conn = sqlite3.connect('advert.db')
        cursor = conn.cursor()
        
        # Базовый запрос
        query = '''
        SELECT id, collection, model, number, price, currency, created_at, user_id, username 
        FROM advertisements 
        WHERE status = 'active'
        '''
        
        # Параметры для фильтрации
        params = []
        
        # Добавляем условия фильтрации
        if collection_filter:
            query += ' AND collection = ?'
            params.append(collection_filter)
            
            if model_filter:
                query += ' AND model = ?'
                params.append(model_filter)
        
        # Сортировка
        query += ' ORDER BY created_at DESC'
        
        # Выполняем запрос
        cursor.execute(query, params)
        ads = cursor.fetchall()
        conn.close()
        
        # Форматируем данные для отображения
        ads_list = []
        for ad in ads:
            ad_id, collection, model, number, price, currency, created_at, user_id, username = ad
    
            price_str = f"{price} {currency}"

            ads_list.append({
                'id': ad_id,
                'collection': collection,
                'model': model,
                'number': number,
                'price': price_str,
                'currency': currency,
                'original_price': price,
                'user_id': user_id,
                'username': username
            })
        
        return jsonify({'success': True, 'ads': ads_list})
        
    except Exception as e:
        print(f"Error fetching active ads: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/get_user_ads', methods=['POST'])
def get_user_ads():
    
    # Get user_id from request
    user_data = request.get_json()
    if not user_data:
        return jsonify({'success': False, 'error': 'No data provided'}), 400
        
    user_id = user_data.get('user_id')
    
    if not user_id:
        return jsonify({'success': False, 'error': 'User ID not provided'}), 400
    
    try:
        # Connect to database
        conn = sqlite3.connect('advert.db')
        cursor = conn.cursor()
        
        # Get user's ads (only active ones)
        cursor.execute('''
        SELECT id, collection, model, number, price, currency, created_at 
        FROM advertisements 
        WHERE user_id = ? AND status = 'active'
        ORDER BY created_at DESC
        ''', (user_id,))
        
        ads = cursor.fetchall()
        conn.close()
        
        # Format the ads data for display
        ads_list = []
        for ad in ads:
            ad_id, collection, model, number, price, currency, created_at = ad
            
            # Format price with currency
            price_str = f"{price} {currency}"
            
            ads_list.append({
                'id': ad_id,
                'collection': collection,
                'model': model,
                'number': number,
                'price': price_str,
                'currency': currency,
                'original_price': price
            })
        
        return jsonify({'success': True, 'ads': ads_list})
        
    except Exception as e:
        print(f"Error fetching user ads: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/webapp', methods=['GET'])
def webapp():
    # Получаем данные пользователя из Telegram WebApp
    init_data = request.args.get('tgWebAppData')
    print("Raw init_data:", init_data)  # Логируем сырые данные
    
    user = parse_webapp_data(init_data) if init_data else None
    print("Parsed user:", user)  # Логируем распарсенные данные
    
    if user and 'id' in user:
        # Добавляем логирование перед сохранением
        print(f"Saving user: ID={user.get('id')}, Name={user.get('first_name')}, "
              f"Surname={user.get('last_name')}, Username=@{user.get('username')}")
        
        # Добавляем/проверяем пользователя в базе
        success = check_and_add_user(
            user_id=user.get('id'),
            name=user.get('first_name'),
            surname=user.get('last_name'),
            username=user.get('username')
        )
        
        if not success:
            print("Failed to save user data to database")
    
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Telegram Mini-App</title>
        <script src="https://telegram.org/js/telegram-web-app.js"></script>
        <script src="https://unpkg.com/@tonconnect/sdk@latest/dist/tonconnect-sdk.min.js"></script>
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
        <style>
            .toggle-advanced-btn {
                width: 40px;
                height: 40px;
                border-radius: 50%;
                background: #f0f0f0;
                border: none;
                display: flex;
                align-items: center;
                justify-content: center;
                cursor: pointer;
                transition: all 0.2s ease;
            }

            .toggle-advanced-btn:hover {
                background: #e0e0e0;
            }

            .toggle-advanced-btn i {
                font-size: 16px;
                color: #555;
                transition: transform 0.3s ease;
            }
            #sort-select,
            #min-price,
            #max-price {
                max-width: 140px;
            }
            .filters-container {
                height = 100 px;
                padding: 12px 15px;
                background: white;
                position: fixed;
                top: 56px;
                left: 0;
                right: 0;
                z-index: 90;
                box-shadow: 0 2px 5px rgba(0,0,0,0.1);
                border-bottom: 1px solid #eee;
                width: 100%;
                box-sizing: border-box;
            }

            .filter-row {
                display: flex;
                gap: 8px;
                align-items: center;
                width: 100%;
                max-width: 100%;
            }

            #ads-container {
                padding-top: 0 !important;
            }

            .filter-select {
                flex: 1;
                min-width: 0;
                padding: 10px 12px;
                border-radius: 8px;
                border: 1px solid #ddd;
                font-size: 14px;
                appearance: none;
                -webkit-appearance: none;
                -moz-appearance: none;
                background-image: url("data:image/svg+xml;charset=UTF-8,%3csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3e%3cpolyline points='6 9 12 15 18 9'%3e%3c/polyline%3e%3c/svg%3e");
                background-repeat: no-repeat;
                background-position: right 10px center;
                background-size: 1em;
                transition: all 0.2s ease;
            }

            .filter-select:focus {
                outline: none;
                border-color: #0088cc;
                box-shadow: 0 0 0 2px rgba(0, 136, 204, 0.2);
            }

            .clear-filters-btn {
                width: 40px;
                height: 40px;
                border-radius: 50%;
                background: #f0f0f0;
                border: none;
                display: flex;
                align-items: center;
                justify-content: center;
                cursor: pointer;
                transition: all 0.2s ease;
            }

            .clear-filters-btn:hover {
                background: #e0e0e0;
            }

            .clear-filters-btn i {
                font-size: 16px;
                color: #555;
            }

            body.dark .filters-container {
                background: #333;
                border-bottom-color: #444;
            }

            body.dark .filter-select {
                background-color: #444;
                color: white;
                border-color: #555;
            }

            body.dark .clear-filters-btn {
                background: #555;
            }

            body.dark .clear-filters-btn i {
                color: #eee;
            }

            .ad-seller {
                font-size: 12px;
                color: #666;
                margin-top: 4px;
                white-space: nowrap;
                overflow: hidden;
                text-overflow: ellipsis;
            }
            .ad-grid {
                display: grid;
                grid-template-columns: repeat(2, 1fr);
                gap: 12px;
                padding: 12px;
            }

            .ad-card {
                background: white;
                border-radius: 12px;
                overflow: hidden;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                display: flex;
                flex-direction: column;
            }

            # .ad-image {
            #     width: 100%;
            #     aspect-ratio: 1;
            #     background-color: #f0f0f0;
            #     display: flex;
            #     align-items: center;
            #     justify-content: center;
            #     color: #888;
            #     font-size: 14px;
            # }

            .ad-details {
                padding: 12px;
                display: flex;
                flex-direction: column;
                gap: 4px;
            }

            .ad-collection {
                font-weight: bold;
                font-size: 14px;
                white-space: nowrap;
                overflow: hidden;
                text-overflow: ellipsis;
            }

            .ad-model {
                font-size: 13px;
                color: #666;
                white-space: nowrap;
                overflow: hidden;
                text-overflow: ellipsis;
            }

            .ad-number {
                font-size: 12px;
                color: #888;
            }

            .ad-price-container {
                margin-top: 8px;
                text-align: right;
            }

            .ad-price {
                font-weight: bold;
                color: #0088cc;
                white-space: pre-line;
            }

            .buy-btn {
                width: 100%;
                padding: 6px 8px;
                margin-top: 8px;
                color: white;
                border: none;
                border-radius: 5px;
                cursor: pointer;
                font-weight: bold;
                font-size: 13px;
                transition: background-color 0.3s;
                line-height: 1.3;
                min-height: 36px;
                display: flex;
                flex-direction: column;
                justify-content: center;
                align-items: center;
            }

            .buy-btn.ton {
                background-color: #0088cc; /* Синий для TON */
            }

            .buy-btn.ton:hover {
                background-color: #0077bb;
            }

            .buy-btn.usdt {
                background-color: #4CAF50; /* Зеленый для USDT */
            }

            .buy-btn.usdt:hover {
                background-color: #45a049;
            }

            .price-change {
                font-size: 10px;
                color: #ffdddd;
                margin-left: 2px;
                display: inline-block;
            }

            .no-ads {
                text-align: center;
                padding: 30px;
                color: #888;
            }

            .create-ad-btn {
                width: 100%;
                max-width: 200px;
                margin: 15px auto 0;
                padding: 12px;
                background: #4CAF50;
                color: white;
                border: none;
                border-radius: 8px;
                font-weight: bold;
                display: block;
            }
            body {
                font-family: Arial, sans-serif;
                margin: 0;
                padding: 0;
                background-color: #f5f5f5;
                display: flex;
                flex-direction: column;
                min-height: 100vh;
            }
            .header {
                height = 100px;
                display: flex;
                justify-content: space-between;
                align-items: center;
                padding: 10px 15px;
                background: white;
                box-shadow: 0 2px 5px rgba(0,0,0,0.1);
                position: sticky;
                top: 0;
                z-index: 100;
                gap: 10px;
            }
            .wallet-btn {
                background-color: #0088cc;
                color: white;
                border: none;
                padding: 8px 15px;
                border-radius: 20px;
                cursor: pointer;
                font-size: 14px;
                margin: 0 5px;
                white-space: nowrap;
            }
            .settings-btn {
                background: none;
                border: none;
                color: #555;
                width: 36px;
                height: 36px;
                font-size: 18px;
                cursor: pointer;
                padding: 5px;
                margin: 0 5px;
                transition: none !important;
            }
            .settings-btn:hover {
                background: none !important;
            }
            .settings-btn:active {
                transform: scale(0.95);
            }
            .user-avatar {
                width: 36px;
                height: 36px;
                border-radius: 50%;
                object-fit: cover;
            }
            .container {
                width: 100%;
                max-width: 100%;
                margin: 0 auto;
                background: white;
                padding: 20px;
                box-sizing: border-box;
                flex: 1;
                display: flex;
                flex-direction: column;
            }
            .content {
                flex: 1;
                padding: 20px;
                box-sizing: border-box;
                width: 100%;
                overflow-y: auto;
            }
            .content-section {
                width: 100%;
                min-height: 100%;
                display: none;
                padding: 0;
            }
            .content-section.active {
                display: block;
            }
            button {
                background-color: #0088cc;
                color: white;
                border: none;
                padding: 10px 15px;
                border-radius: 5px;
                cursor: pointer;
                margin-top: 10px;
                width: 100%;
                max-width: 300px;
            }
            button:hover {
                background-color: #0077bb;
            }
            .menu {
                display: flex;
                justify-content: space-around;
                position: sticky;
                bottom: 0;
                left: 0;
                right: 0;
                background: white;
                padding: 10px 0;
                box-shadow: 0 -2px 5px rgba(0,0,0,0.1);
            }
            .menu-button {
                flex: 1;
                margin: 0 5px;
                text-align: center;
                padding: 10px;
                border-radius: 5px;
                background: #f0f0f0;
                cursor: pointer;
                transition: all 0.3s ease;
            }
            .menu-button.active {
                background: #0088cc;
                color: white;
            }
            h1 {
                margin-top: 0;
            }
            .profile-item {
                display: flex;
                justify-content: space-between;
                align-items: center;
                padding: 12px 0;
                border-bottom: 1px solid #eee;
                cursor: pointer;
            }
            .profile-item:last-child {
                border-bottom: none;
            }
            .profile-item-title {
                font-weight: bold;
                color: #333;
            }
            .empty-state {
                text-align: center;
                padding: 30px 0;
                color: #888;
            }
            .collection-select, .model-select, .number-input, .price-input {
                width: 100%;
                padding: 12px;
                margin: 10px 0;
                border-radius: 8px;
                border: 1px solid #ddd;
                font-size: 16px;
                background-color: white;
                box-sizing: border-box;
            }
            .collection-select, .model-select, .currency-select {
                appearance: none;
                -webkit-appearance: none;
                -moz-appearance: none;
                background-image: url("data:image/svg+xml;charset=UTF-8,%3csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3e%3cpolyline points='6 9 12 15 18 9'%3e%3c/polyline%3e%3c/svg%3e");
                background-repeat: no-repeat;
                background-position: right 10px center;
                background-size: 1em;
            }
            .price-container {
                display: flex;
                gap: 10px;
                align-items: center;
            }
            .price-input {
                flex: 1;
            }
            .currency-select {
                width: 100px;
                padding: 12px;
                border-radius: 8px;
                border: 1px solid #ddd;
                font-size: 16px;
                background-color: white;
            }
            .create-ad-form {
                padding: 15px;
                background: white;
                border-radius: 10px;
                box-shadow: 0 2px 5px rgba(0,0,0,0.1);
            }
            .form-title {
                font-size: 18px;
                font-weight: bold;
                margin-bottom: 15px;
                text-align: center;
            }
            .form-actions {
                display: flex;
                gap: 10px;
                margin-top: 15px;
            }
            .create-btn {
                background-color: #4CAF50;
                flex: 1;
            }
            .create-btn:disabled {
                background-color: #cccccc;
                cursor: not-allowed;
            }
            .cancel-btn {
                background-color: #f44336;
                flex: 1;
            }
            @media (max-width: 480px) {
                .container {
                    padding: 10px;
                }
                .content {
                    padding: 10px;
                }
                .collection-select, .model-select, .number-input, .price-input, .currency-select {
                    font-size: 14px;
                    padding: 10px;
                }
                .currency-select {
                    width: 80px;
                }
            }
        </style>
    </head>
    <body>
        <div class="header">
            <button id = 'connect-btn' class="wallet-btn" onclick="connectWallet()">Connect wallet</button>
            <button class="settings-btn" onclick="openSettings()">
                <i class="fas fa-cog"></i>
            </button>
            <img id="user-avatar" class="user-avatar" src="https://via.placeholder.com/36" alt="User Avatar">
        </div>

        <div class="container">
            <div class="content">
                <div id="market" class="content-section active">
                    <!-- Фиксированный контейнер фильтров -->
                    <div class="filters-container">
                        <div class="filter-row">
                            <select id="collection-filter" class="filter-select" onchange="updateCollectionFilter(this.value)">
                                <option value="">All collections</option>
                            </select>

                            <select id="model-filter" class="filter-select" disabled>
                                <option value="">All models</option>
                            </select>

                            <!-- Кнопка показа/скрытия -->
                            <button id="toggle-advanced-btn" class="toggle-advanced-btn" onclick="toggleAdvancedFilters()">
                                <i class="fas fa-chevron-down"></i>
                            </button>

                            <!-- Очистка -->
                            <button class="clear-filters-btn" onclick="clearFilters()">
                                <i class="fas fa-times"></i>
                            </button>
                        </div>
                        <!-- Вторая строка: сортировка и диапазон цен -->
                        <div id="advanced-filters" class="filter-row" style="margin-top: 8px; display: none;">
                            <select id="sort-select" class="filter-select" onchange="filterAds()">
                                <option value="">Sort by</option>
                                <option value="price-asc">Price: Low to High</option>
                                <option value="price-desc">Price: High to Low</option>
                                <option value="number-asc">Number #: Ascending</option>
                                <option value="number-desc">Number #: Descending</option>
                            </select>

                            <input type="number" id="min-price" class="filter-select" placeholder="Min Price" oninput="filterAds()">
                            <input type="number" id="max-price" class="filter-select" placeholder="Max Price" oninput="filterAds()">
                        </div>
                    </div>
                    
                    <!-- Контейнер для объявлений с отступом сверху -->
                    <div id="filters-spacer" style="height: 56px;"></div>
                    <div id="ads-container">
                        <!-- Здесь будут отображаться объявления -->
                    </div>
                </div>
                    
                <div id="profile" class="content-section">
                    <div id="profile-data"></div>
                    <div id="profile-actions" class="profile-actions">
                        <div class="profile-item" onclick="navigateTo('my-ads')">
                            <span class="profile-item-title">My ads</span>
                        </div>
                        <div class="profile-item" onclick="showCreateAdForm()">
                            <span class="profile-item-title">Create an ad</span>
                        </div>
                        <div class="profile-item" onclick="navigateTo('notifications')">
                            <span class="profile-item-title">Notifications</span>
                        </div>
                        <div class="profile-item" onclick="navigateTo('faq')">
                            <span class="profile-item-title">FAQ</span>
                        </div>
                        <div class="profile-item" onclick="navigateTo('deals')">
                            <span class="profile-item-title">My deals</span>
                        </div>
                    </div>
                    <div class="empty-state">
                        Your active trades will appear here
                    </div>
                </div>
                <div id="stats" class="content-section">
                    <div id="stats-data"></div>
                </div>
            </div>
        </div>

        <div class="menu">
            <div class="menu-button active" onclick="switchTab('market')">Market</div>
            <div class="menu-button" onclick="switchTab('profile')">Profile</div>
            <div class="menu-button" onclick="switchTab('stats')">Statistics</div>
        </div>

        <script>
            console.log('Telegram WebApp initialized:', window.Telegram && window.Telegram.WebApp);
            const tg = window.Telegram.WebApp;
            
            tg.expand();
            tg.MainButton.hide();
            
            // Устанавливаем тему
            updateTheme();
            
            // Получаем данные пользователя
            const user = tg.initDataUnsafe?.user;
            if (user) {
                // Сохраняем пользователя
                fetch('/save_user', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        user_id: user.id,
                        name: user.first_name,
                        surname: user.last_name,
                        username: user.username
                    })
                }).then(response => response.json())
                .then(data => {
                    if (!data.success) {
                        console.error('Error saving user:', data.error);
                    }
                });
                
                // Загружаем данные пользователя
                loadUserData(user.id);
            }
            function loadUserData(userId) {
                fetch('/get_user_data', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ user_id: userId })
                }).then(response => response.json())
                .then(data => {
                    if (data.success) {
                        // Обновляем интерфейс с данными пользователя
                        updateUserProfile(data.data);
                    }
                });
            }
            function updateUserProfile(userData) {
                // Здесь можно обновить интерфейс с данными пользователя
                console.log('User data loaded:', userData);
            }
            if (user) {
                if (user.photo_url) {
                    document.getElementById('user-avatar').src = user.photo_url;
                }
                updateTheme();
            }
            
            // Загружаем активные объявления сразу при загрузке
            document.addEventListener('DOMContentLoaded', function() {
                setTimeout(() => {
                    if (document.getElementById('market').classList.contains('active')) {
                        loadMarketData();
                    }
                }, 100);
            });
            
            // Модели для коллекций
            const collectionModels = {
                'Ric Flair': ['Ric Flair'],
                'Cattea Life': ['Cattea Chaos'],
                'Lazy & Rich': ['Sloth Capital', 'Chill or thrill'],
                'PUCCA': ['PUCCA Moods'],
                'Kudai': ['GMI', 'NGMI'],
                'Lost Dogs': ['Magic of the Way', 'Lost Memeries'],
                'Bored Stickers': ['CNY 2092', '2092', '3151', '3278', '4017', '5824', '6527', '9287', '9765', '9780'],
                'Blum': ['Cap', 'Cat', 'Bunny', 'No', 'General', 'Worker', 'Cook', 'Curly'],
                'Smeshariki': ['Chamomile Valley'],
                'WAGMI HUB': ['EGG & HAMMER', 'WAGMI AI AGENT'],
                'Doodles': ['Doodles Dark Mode'],
                'Flappy Bird': ['Well known one', 'Blue Wings', 'Light Glide', 'Frost Flap', 'Blush Flight', 'Ruby Wings'],
                'SUNDOG': ['TO THE SUN'],
                'Lil Pudgys': ['Lil Pudgys x Baby Shark'],
                'Not Pixel': ['Random memes', 'Cute pack', 'Grass Pixel', 'Mac Pixel', 'Super Pixel', 'DOGS Pixel', 'Diamond Pixel', 'Pixanos', 'Retro Pixel', 'Error Pixel', 'Vice Pixel', 'Pixioznik', 'Zompixel', 'Pixel phrases', 'Films memes', 'Smileface pack', 'Tournament S1'],
                'BabyDoge': ['Mememania'],
                'Pudgy & Friends': ['Pengu x Baby Shark'],
                'Pudgy Penguins': ['Pengu Valentines', 'Blue Pengu', 'Cool Blue Pengu', 'Pengu CNY'],
                'DOGS OG': ['Not Cap', 'Not Coin', 'Panama Hat', 'Toddler', 'Cherry Glasses', 'Dogtor', 'Kamikaze', 'King', 'Blue Eyes Hat', 'Emo Boy', 'Cyclist', 'Scary Eyes', 'Nose Glasses', 'Strawberry Hat', 'Gnome', 'One Piece Sanji', 'Diver', 'Robber', 'Sheikh', 'Bow Tie', 'Hypnotist', 'Witch', 'Teletubby', 'Tin Foil Hat', 'Cook', 'Tubeteyka', 'Alumni', 'Anime Ears', 'Scarf', 'Bodyguard', 'Tank Driver', 'Asterix', 'Nerd', 'Tattoo Artist', 'Pilot', 'Jester', 'Van Dogh', 'Baseball Cap', 'Green Hair', 'Smile', 'Gentleman', 'Baseball Bat', 'Alien', 'Sherlock Holmes', 'Extra Eyes', 'Dog Tyson', 'Termidogtor', 'Frog Hat', 'Ushanka', 'Sock Head', 'Noodles', 'Ice Cream', 'Shaggy', 'Pink Bob', 'Viking', 'Knitted Hat', 'Toast Bread', 'Princess', 'Santa Dogs', 'Newsboy Cap', 'Google Intern Hat', 'Orange Hat', 'Hello Kitty', 'Sharky Dog', 'Frog Glasses', 'Duck', 'KFC', 'Unicorn']
            };
            
            // Список всех коллекций
            const allCollections = Object.keys(collectionModels).sort();

            // Функция для инициализации фильтров
            function initFilters() {
                const collectionFilter = document.getElementById('collection-filter');
                
                // Заполняем фильтр коллекций
                allCollections.forEach(collection => {
                    const option = document.createElement('option');
                    option.value = collection;
                    option.textContent = collection;
                    collectionFilter.appendChild(option);
                });
                
                // Обработчик изменения фильтра коллекций
                collectionFilter.addEventListener('change', function() {
                    const modelFilter = document.getElementById('model-filter');
                    
                    if (this.value) {
                        modelFilter.disabled = false;
                        updateModelFilterOptions(this.value);
                    } else {
                        modelFilter.disabled = true;
                        modelFilter.innerHTML = '<option value="">All models</option>';
                    }
                    
                    filterAds();
                });
                
                // Обработчик изменения фильтра моделей
                document.getElementById('model-filter').addEventListener('change', filterAds);
            }

            async function saveAdToDatabase(adData) {
                try {
                    const response = await fetch('/save_ad', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify(adData)
                    });
                    
                    const result = await response.json();
                    if (result.success) {
                        console.log('The ad has been successfully saved to the database');
                        return true;
                    } else {
                        console.error('Error saving ad:', result.error);
                        return false;
                    }
                } catch (error) {
                    console.error('Error sending data:', error);
                    return false;
                }
            }

            function updateTheme() {
                const isDark = tg.colorScheme === 'dark';
                document.body.style.backgroundColor = isDark ? '#1f1f1f' : '#f5f5f5';
                document.body.style.color = isDark ? 'white' : 'black';
                
                if (isDark) {
                    document.body.classList.add('dark');
                } else {
                    document.body.classList.remove('dark');
                }
                
                // Обновляем стили фильтров
                document.querySelectorAll('.filter-select').forEach(el => {
                    el.style.backgroundColor = isDark ? '#444' : 'white';
                    el.style.color = isDark ? 'white' : 'black';
                    el.style.borderColor = isDark ? '#555' : '#ddd';
                });
                
                // Обновляем стили выпадающих списков и инпутов
                document.querySelectorAll('.collection-select, .model-select, .number-input, .price-input, .currency-select').forEach(el => {
                    el.style.backgroundColor = isDark ? '#333' : 'white';
                    el.style.color = isDark ? 'white' : 'black';
                    el.style.borderColor = isDark ? '#555' : '#ddd';
                });
            }
            
            async function connectWallet() {
                const connector = new TonConnectSDK.TonConnect({
                    manifest: "https://raw.githubusercontent.com/ArsK123141/json/refs/heads/main/tonconnect-manifest.json?token=GHSAT0AAAAAADC3WJOZRQBEZZ7S3UI7PUOM2AMPHEA"
                });

                try {
                    await connector.restoreConnection();

                    const connected = await connector.connectWallet();

                    if (connected && connected.account) {
                        const walletAddress = connected.account.address;
                        tg.showAlert(`Wallet connected:\n${walletAddress}`);
                        console.log("Wallet connected:", walletAddress);

                        // здесь можно отправить walletAddress на бэкенд
                    } else {
                        tg.showAlert("Connection failed");
                    }
                } catch (e) {
                    console.error("TON Connect error:", e);
                    tg.showAlert("Error connecting wallet");
                }
            }

            
            function openSettings() {
                tg.showPopup({
                    title: 'Settings',
                    message: 'Здесь будут настройки приложения',
                    buttons: [
                        {id: 'ok', type: 'default', text: 'OK'}
                    ]
                });
            }
            
            function switchTab(tabName) {
                // Убираем активный класс у всех кнопок
                document.querySelectorAll('.menu-button').forEach(btn => {
                    btn.classList.remove('active');
                    btn.style.background = tg.colorScheme === 'dark' ? '#333' : '#f0f0f0';
                    btn.style.color = tg.colorScheme === 'dark' ? 'white' : 'black';
                });
                
                // Добавляем активный класс текущей кнопке
                const activeBtn = event.target;
                activeBtn.classList.add('active');
                activeBtn.style.background = '#0088cc';
                activeBtn.style.color = 'white';
                
                // Переключаем контент
                document.querySelectorAll('.content-section').forEach(section => {
                    section.classList.remove('active');
                });
                document.getElementById(tabName).classList.add('active');
                
                if (tabName === 'market') {
                    loadMarketData();
                } else if (tabName === 'profile') {
                    loadProfileData();
                } else if (tabName === 'stats') {
                    loadStatsData();
                }
            }
            
            // Обновление списка моделей в фильтре
            function updateModelFilterOptions(collection) {
                const modelFilter = document.getElementById('model-filter');
                modelFilter.innerHTML = '<option value="">All models</option>';
                
                if (collection && collectionModels[collection]) {
                    collectionModels[collection].forEach(model => {
                        const option = document.createElement('option');
                        option.value = model;
                        option.textContent = model;
                        modelFilter.appendChild(option);
                    });
                }
            }

            // Фильтрация объявлений
            function filterAds() {
                const collectionFilter = document.getElementById('collection-filter').value;
                const modelFilter = document.getElementById('model-filter').value;
                const sortOption = document.getElementById('sort-select').value;
                const minPrice = parseFloat(document.getElementById('min-price').value) || 0;
                const maxPrice = parseFloat(document.getElementById('max-price').value) || Infinity;

                const cards = Array.from(document.querySelectorAll('.ad-card'));

                // Сортировка
                if (sortOption) {
                    cards.sort((a, b) => {
                        const priceA = parseFloat(a.querySelector('.buy-btn').textContent);
                        const priceB = parseFloat(b.querySelector('.buy-btn').textContent);
                        const numberA = parseInt(a.querySelector('.ad-number').textContent.replace('#', '')) || 0;
                        const numberB = parseInt(b.querySelector('.ad-number').textContent.replace('#', '')) || 0;

                        switch (sortOption) {
                            case 'price-asc': return priceA - priceB;
                            case 'price-desc': return priceB - priceA;
                            case 'number-asc': return numberA - numberB;
                            case 'number-desc': return numberB - numberA;
                        }
                    });

                    const grid = document.querySelector('.ad-grid');
                    cards.forEach(card => grid.appendChild(card)); // перестраиваем порядок
                }

                cards.forEach(card => {
                    const collection = card.querySelector('.ad-collection').textContent;
                    const model = card.querySelector('.ad-model').textContent;
                    const price = parseFloat(card.getAttribute('data-price-usdt')) || 0;
                    const matchesCollection = !collectionFilter || collection === collectionFilter;
                    const matchesModel = !modelFilter || model === modelFilter;
                    const matchesPrice = price >= minPrice && price <= maxPrice;

                    card.style.display = (matchesCollection && matchesModel && matchesPrice) ? 'flex' : 'none';
                });

                document.getElementById('ads-container').scrollTo(0, 0);
            }

            // Функция для очистки фильтров
            function clearFilters() {
                document.getElementById('collection-filter').value = '';
                document.getElementById('model-filter').value = '';
                document.getElementById('model-filter').disabled = true;
                filterAds();
                
                // Добавляем анимацию для кнопки очистки
                const clearBtn = document.querySelector('.clear-filters-btn');
                clearBtn.style.transform = 'scale(0.9)';
                setTimeout(() => {
                    clearBtn.style.transform = 'scale(1)';
                }, 200);
            }

            async function loadMarketData() {
                // Показываем индикатор загрузки
                requestAnimationFrame(() => {
                    const header = document.querySelector('.header');
                    const filters = document.querySelector('.filters-container');
                    const adsContainer = document.getElementById('ads-container');

                    if (header && filters && adsContainer) {
                        const totalOffset = header.offsetHeight + filters.offsetHeight;
                        adsContainer.style.paddingTop = `${totalOffset}px`;
                    }
                });
                document.getElementById('ads-container').innerHTML = '<p>Loading ads...</p>';
                
                try {
                    const response = await fetch('/get_active_ads', {
                        method: 'GET',
                        headers: {
                            'Content-Type': 'application/json',
                        }
                    });
                    
                    const result = await response.json();
                    
                    if (result.success) {
                        if (result.ads && result.ads.length > 0) {
                            let adsHtml = '<div class="ad-grid">';
                            
                            result.ads.forEach(ad => {
                                adsHtml += `
                                    <div class="ad-card" data-price-usdt="${ad.price_usdt}">
                                        <div class="ad-image">
                                            <!-- Здесь будет изображение -->
                                        </div>
                                        <div class="ad-details">
                                            <div class="ad-collection">${ad.collection}</div>
                                            <div class="ad-model">${ad.model}</div>
                                            <div class="ad-number">#${ad.number}</div>
                                            <button class="buy-btn ${ad.currency === 'USDT' ? 'usdt' : 'ton'}" onclick="buyAd(${ad.id})">
                                                ${ad.price}
                                            </button>
                                        </div>
                                    </div>
                                `;
                            });
                            
                            adsHtml += '</div>';
                            document.getElementById('ads-container').innerHTML = adsHtml;
                            // Применяем отступ только к .ad-grid
                            document.getElementById('ads-container').innerHTML = adsHtml;

                            // Гарантируем, что элементы успели отрисоваться
                            
                            // Инициализируем фильтры после загрузки данных
                            initFilters();
                        } else {
                            document.getElementById('ads-container').innerHTML = `
                                <div class="no-ads">
                                    <p>No active ads</p>
                                </div>
                            `;
                        }
                    } else {
                        document.getElementById('ads-container').innerHTML = '<p>Error loading ads</p>';
                        tg.showAlert('Error loading ads: ' + (result.error || 'Неизвестная ошибка'));
                    }
                } catch (error) {
                    console.error('Error fetching market ads:', error);
                    document.getElementById('ads-container').innerHTML = '<p>Error loading ads</p>';
                    tg.showAlert('There was an error loading ads');
                }
            }

            function loadProfileData() {
                const user = tg.initDataUnsafe?.user;
                if (user) {
                    let profileHtml = `
                        <p><strong>Имя:</strong> ${user.first_name || 'Не указано'}</p>
                        <p><strong>Фамилия:</strong> ${user.last_name || 'Не указана'}</p>
                        <p><strong>Username:</strong> ${user.username ? '@' + user.username : 'Не указан'}</p>
                    `;
                    document.getElementById('profile-data').innerHTML = profileHtml;
                }
                
                // Восстанавливаем стандартные действия профиля
                document.getElementById('profile-actions').innerHTML = `
                    <div class="profile-item" onclick="navigateTo('my-ads')">
                        <span class="profile-item-title">My ads</span>
                    </div>
                    <div class="profile-item" onclick="showCreateAdForm()">
                        <span class="profile-item-title">Create an ad</span>
                    </div>
                    <div class="profile-item" onclick="navigateTo('notifications')">
                        <span class="profile-item-title">Notifications</span>
                    </div>
                    <div class="profile-item" onclick="navigateTo('faq')">
                        <span class="profile-item-title">FAQ</span>
                    </div>
                    <div class="profile-item" onclick="navigateTo('deals')">
                        <span class="profile-item-title">My deals</span>
                    </div>
                `;
                
                // Восстанавливаем empty state
                document.querySelector('.empty-state').style.display = 'block';
            }
            
            function loadStatsData() {
                document.getElementById('stats-data').innerHTML = `
                    <p>Статистика загружается...</p>
                `;
            }
            
            function navigateTo(page) {
                if (page === 'my-ads') {
                    showMyAds();
                } else {
                    tg.showAlert(`Переход на страницу: ${page}`);
                }
            }

            async function showMyAds() {
                const user = tg.initDataUnsafe?.user;
                if (!user || !user.id) {
                    tg.showAlert('Failed to retrieve user data');
                    return;
                }

                // Show loading state
                document.getElementById('profile-data').innerHTML = '<p>Loading your ads...</p>';
                document.getElementById('profile-actions').innerHTML = '';
                document.querySelector('.empty-state').style.display = 'none';

                try {
                    const response = await fetch('/get_user_ads', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify({ user_id: user.id })
                    });
                    
                    const result = await response.json();
                    
                    if (result.success) {
                        if (result.ads && result.ads.length > 0) {
                            let adsHtml = '<div class="ad-grid">';
                            
                            result.ads.forEach(ad => {
                                adsHtml += `
                                    <div class="ad-card">
                                        <div class="ad-image">
                                            
                                        </div>
                                        <div class="ad-details">
                                            <div class="ad-collection">${ad.collection}</div>
                                            <div class="ad-model">${ad.model}</div>
                                            <div class="ad-number">#${ad.number}</div>
                                            <div class="ad-price-container">
                                                <div class="ad-price">
                                                    ${ad.price}
                                                </div>
                                            </div>
                                            <button class="delete-btn" onclick="window.deleteAd(${ad.id})" 
                                                    style="width: 100%; padding: 8px; background: #f44336; color: white; border: none; border-radius: 5px; cursor: pointer; margin-top: 8px;">
                                                Удалить
                                            </button>
                                        </div>
                                    </div>
                                `;
                            });
                            
                            adsHtml += '</div>';
                            document.getElementById('profile-data').innerHTML = adsHtml;
                        } else {
                            document.getElementById('profile-data').innerHTML = `
                                <div class="no-ads">
                                    <p>You don't have any ads yet.</p>
                                    <button class="create-ad-btn" onclick="showCreateAdForm()">
                                        Create an ad
                                    </button>
                                </div>
                            `;
                        }
                    } else {
                        tg.showAlert('Error loading ads: ' + (result.error || 'Unknown error'));
                        loadProfileData();
                    }
                } catch (error) {
                    console.error('Error fetching user ads:', error);
                    tg.showAlert('There was an error loading ads');
                    loadProfileData();
                }
            }
            
            async function deleteAd(adId) {
                const user = tg.initDataUnsafe?.user;
                if (!user || !user.id) {
                    tg.showAlert('Failed to retrieve user data');
                    return;
                }

                tg.showPopup({
                    title: 'Deletion confirmation',
                    message: 'Are you sure you want to delete this ad?',
                    buttons: [
                        {id: 'confirm', type: 'destructive', text: 'Delete'},
                        {id: 'cancel', type: 'cancel'}
                    ]
                }, async function(btnId) {
                    if (btnId === 'confirm') {
                        try {
                            const response = await fetch('/delete_ad', {
                                method: 'POST',
                                headers: {
                                    'Content-Type': 'application/json',
                                },
                                body: JSON.stringify({
                                    ad_id: adId,
                                    user_id: user.id
                                })
                            });
                            
                            const result = await response.json();
                            
                            if (result.success) {
                                tg.showAlert('The ad has been successfully removed!');
                                showMyAds();
                            } else {
                                tg.showAlert('Error: ' + (result.error || 'Unknown error'));
                            }
                        } catch (error) {
                            console.error('Error:', error);
                            tg.showAlert('There was an error deleting the ad.');
                        }
                    }
                });
            }

            window.editAd = async function(adId, currentPrice) {
                console.log('editAd called with:', adId, currentPrice); // Отладочное сообщение
                
                if (!window.Telegram || !window.Telegram.WebApp) {
                    console.error('Telegram WebApp not initialized');
                    return;
                }
                
                const tg = window.Telegram.WebApp;
                const user = tg.initDataUnsafe?.user;
                
                if (!user || !user.id) {
                    tg.showAlert('Failed to retrieve user data');
                    return;
                }

                try {
                    // Создаем HTML для формы редактирования
                    const editFormHtml = `
                        <div style="padding: 15px;">
                            <div style="margin-bottom: 15px;">
                                <label style="display: block; margin-bottom: 5px; font-weight: bold;">Новая цена:</label>
                                <input type="text" id="new-price-input" value="${currentPrice}" 
                                    style="width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 5px;"
                                    placeholder="Введите новую цену">
                            </div>
                        </div>
                    `;

                    // Показываем форму редактирования
                    tg.showPopup({
                        title: 'Изменение цены',
                        message: editFormHtml,
                        buttons: [
                            {id: 'cancel', type: 'cancel'},
                            {id: 'confirm', type: 'default', text: 'Сохранить'}
                        ]
                    }, function(btnId) {
                        if (btnId === 'confirm') {
                            const newPrice = document.getElementById('new-price-input').value;
                            window.confirmPriceChange(adId, user.id, newPrice);
                        }
                    });
                    
                } catch (error) {
                    console.error('Error in editAd:', error);
                    tg.showAlert('Произошла ошибка при открытии формы редактирования');
                }
            };

            // Новая функция для подтверждения изменения цены
            async function confirmPriceChange(adId, userId) {
                const newPriceInput = document.getElementById('new-price-input');
                const newPrice = newPriceInput.value.trim();
                
                if (!newPrice) {
                    tg.showAlert('Пожалуйста, введите новую цену');
                    return;
                }
                
                if (isNaN(newPrice)) {
                    tg.showAlert('Цена должна быть числом');
                    return;
                }

                try {
                    const response = await fetch('/update_ad_price', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify({
                            ad_id: adId,
                            user_id: userId,
                            new_price: newPrice
                        })
                    });
                    
                    const result = await response.json();
                    
                    if (result.success) {
                        tg.showAlert('Цена успешно обновлена!');
                        tg.close(); // Закрываем попап
                        showMyAds(); // Обновляем список объявлений
                    } else {
                        tg.showAlert('Ошибка: ' + (result.error || 'Неизвестная ошибка'));
                    }
                } catch (error) {
                    console.error('Error:', error);
                    tg.showAlert('Произошла ошибка при обновлении цены');
                }
            }

            function updateModelDropdown(collection) {
                const modelSelect = document.getElementById('model-select');
                modelSelect.innerHTML = '<option value="" disabled selected>Select model</option>';
                
                if (collection && collectionModels[collection]) {
                    collectionModels[collection].forEach(model => {
                        const option = document.createElement('option');
                        option.value = model;
                        option.textContent = model;
                        modelSelect.appendChild(option);
                    });
                }
                checkFormValidity();
            }
            
            function checkFormValidity() {
                const collectionSelect = document.getElementById('collection-select');
                const modelSelect = document.getElementById('model-select');
                const numberInput = document.getElementById('number-input');
                const priceInput = document.getElementById('price-input');
                const createBtn = document.getElementById('create-btn');
                
                const isFormValid = collectionSelect.value && 
                                  modelSelect.value && 
                                  numberInput.value && 
                                  priceInput.value;
                createBtn.disabled = !isFormValid;
            }
            
            function buyAd(adId) {
                if (!tg.initDataUnsafe?.user?.id) {
                    tg.showAlert('To purchase you need to log in');
                    return;
                }
                
                tg.showPopup({
                    title: 'Подтверждение покупки',
                    message: 'Вы уверены, что хотите купить этот товар?',
                    buttons: [
                        {id: 'confirm', type: 'default', text: 'Подтвердить'},
                        {id: 'cancel', type: 'cancel'}
                    ]
                }, async function(btnId) {
                    if (btnId === 'confirm') {
                        try {
                            const response = await fetch('/buy_ad', {
                                method: 'POST',
                                headers: {
                                    'Content-Type': 'application/json',
                                },
                                body: JSON.stringify({
                                    ad_id: adId,
                                    user_id: tg.initDataUnsafe.user.id
                                })
                            });
                            
                            const result = await response.json();
                            
                            if (result.success) {
                                tg.showAlert('Покупка успешно завершена!');
                                // Обновляем список объявлений
                                loadMarketData();
                            } else {
                                tg.showAlert('Ошибка: ' + (result.error || 'Неизвестная ошибка'));
                            }
                        } catch (error) {
                            console.error('Error:', error);
                            tg.showAlert('Произошла ошибка при обработке покупки');
                        }
                    }
                });
            }

            function showCreateAdForm() {
                const collections = Object.keys(collectionModels).sort();
                
                // Очищаем профиль и показываем форму создания
                document.getElementById('profile-data').innerHTML = '';
                document.querySelector('.empty-state').style.display = 'none';
                
                document.getElementById('profile-actions').innerHTML = `
                    <div class="create-ad-form">
                        <div class="form-title">Create a new ad</div>
                        <select class="collection-select" id="collection-select" onchange="updateModelDropdown(this.value)">
                            <option value="" disabled selected>Select a collection</option>
                            ${collections.map(collection => `<option value="${collection}">${collection}</option>`).join('')}
                        </select>
                        <select class="model-select" id="model-select" disabled onchange="checkFormValidity()">
                            <option value="" disabled selected>First select a collection</option>
                        </select>
                        <input type="text" class="number-input" id="number-input" placeholder="Enter number #" oninput="checkFormValidity()">
                        <div class="price-container">
                            <input type="text" class="price-input" id="price-input" placeholder="Specify price" oninput="checkFormValidity()">
                            <select class="currency-select" id="currency-select" onchange="checkFormValidity()">
                                <option value="TON">TON</option>
                            </select>
                        </div>
                        <div class="form-actions">
                            <button class="cancel-btn" onclick="loadProfileData()">Cancel</button>
                            <button id="create-btn" class="create-btn" onclick="createAd()" disabled>Create</button>
                        </div>
                    </div>
                `;
                
                // Добавляем обработчик изменения коллекции
                document.getElementById('collection-select').addEventListener('change', function() {
                    const modelSelect = document.getElementById('model-select');
                    if (this.value) {
                        modelSelect.disabled = false;
                        updateModelDropdown(this.value);
                    } else {
                        modelSelect.disabled = true;
                        modelSelect.innerHTML = '<option value="" disabled selected>First select a collection</option>';
                    }
                    checkFormValidity();
                });
                
                // Обновляем стили для темной темы
                updateTheme();
            }
            
            function toggleAdvancedFilters() {
                const advanced = document.getElementById('advanced-filters');
                const icon = document.querySelector('#toggle-advanced-btn i');
                const spacer = document.getElementById('filters-spacer');

                const isExpanded = advanced.style.display !== 'none';

                if (isExpanded) {
                    // Скрываем
                    advanced.style.display = 'none';
                    icon.style.transform = 'rotate(0deg)';
                    spacer.style.height = '56px'; // Только header + первая строка фильтров
                } else {
                    // Показываем
                    advanced.style.display = 'flex';
                    icon.style.transform = 'rotate(180deg)';
                    spacer.style.height = '106px'; // Header + две строки фильтров
                }
            }


            async function createAd() {
                const collectionSelect = document.getElementById('collection-select');
                const modelSelect = document.getElementById('model-select');
                const numberInput = document.getElementById('number-input');
                const priceInput = document.getElementById('price-input');
                const currencySelect = document.getElementById('currency-select');
                
                const selectedCollection = collectionSelect.value;
                const selectedModel = modelSelect.value;
                const number = numberInput.value;
                const price = priceInput.value;
                const currency = currencySelect.value;
                const userId = user?.id || 'anonymous';
                const username = user?.username || 'anonymous';
                
                if (!selectedCollection) {
                    tg.showAlert('Please select a collection');
                    return;
                }
                
                if (!selectedModel) {
                    tg.showAlert('Please select a model');
                    return;
                }
                
                if (!number) {
                    tg.showAlert('Please enter number');
                    return;
                }
                
                if (!price) {
                    tg.showAlert('Please indicate the price');
                    return;
                }
                
                // Создаем объект с данными объявления
                const adData = {
                    user_id: userId,
                    username: username,
                    collection: selectedCollection,
                    model: selectedModel,
                    number: number,
                    price: price,
                    currency: currency,
                    created_at: new Date().toISOString()
                };
                
                // Пытаемся сохранить объявление в базу данных
                const isSaved = await saveAdToDatabase(adData);
                
                if (isSaved) {
                    tg.showAlert(`Ad successfully created!
Collection: ${selectedCollection}
Model: ${selectedModel}
Number: ${number}
Price: ${price} ${currency}`);
                } else {
                    tg.showAlert('There was an error saving your ad. Please try again later.');
                }
                
                // Восстанавливаем первоначальный вид профиля
                loadProfileData();
            }
            
            window.addEventListener('resize', function() {
                if (document.getElementById('market').classList.contains('active')) {
                    const headerHeight = document.querySelector('.header').offsetHeight;
                    const filtersHeight = document.querySelector('.filters-container').offsetHeight;
                    document.getElementById('ads-container').style.paddingTop = `${headerHeight + filtersHeight}px`;
                }
            });
        </script>
    </body>
    </html>
    """

@app.route('/delete_ad', methods=['POST'])
def delete_ad():
    
    delete_data = request.get_json()
    if not delete_data:
        return jsonify({'success': False, 'error': 'No data provided'}), 400
        
    ad_id = delete_data.get('ad_id')
    user_id = delete_data.get('user_id')
    
    if not ad_id or not user_id:
        return jsonify({'success': False, 'error': 'Missing ad_id or user_id'}), 400
    
    try:
        conn = sqlite3.connect('advert.db')
        cursor = conn.cursor()
        
        # Check if ad belongs to user and is active
        cursor.execute('SELECT user_id FROM advertisements WHERE id = ? AND status = "active"', (ad_id,))
        ad = cursor.fetchone()
        
        if not ad:
            conn.close()
            return jsonify({'success': False, 'error': 'Объявление не найдено или уже удалено'}), 404
            
        if str(ad[0]) != str(user_id):
            conn.close()
            return jsonify({'success': False, 'error': 'Вы не можете удалить это объявление'}), 403
        
        # Update status to 'deleted'
        cursor.execute('UPDATE advertisements SET status = "deleted" WHERE id = ?', (ad_id,))
        conn.commit()
        conn.close()
        
        return jsonify({'success': True})
        
    except Exception as e:
        print(f"Error deleting ad: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/update_ad_price', methods=['POST'])
def update_ad_price():
    
    update_data = request.get_json()
    if not update_data:
        return jsonify({'success': False, 'error': 'No data provided'}), 400
        
    ad_id = update_data.get('ad_id')
    user_id = update_data.get('user_id')
    new_price = update_data.get('new_price')
    
    if not ad_id or not user_id or not new_price:
        return jsonify({'success': False, 'error': 'Missing required fields'}), 400
    
    try:
        # Проверяем, что новая цена - число
        float(new_price)
    except ValueError:
        return jsonify({'success': False, 'error': 'Цена должна быть числом'}), 400
    
    try:
        conn = sqlite3.connect('advert.db')
        cursor = conn.cursor()
        
        # Check if ad belongs to user and is active
        cursor.execute('SELECT user_id FROM advertisements WHERE id = ? AND status = "active"', (ad_id,))
        ad = cursor.fetchone()
        
        if not ad:
            conn.close()
            return jsonify({'success': False, 'error': 'Объявление не найдено или уже удалено'}), 404
            
        if str(ad[0]) != str(user_id):
            conn.close()
            return jsonify({'success': False, 'error': 'Вы не можете изменить это объявление'}), 403
        
        # Update price
        cursor.execute('UPDATE advertisements SET price = ? WHERE id = ?', (new_price, ad_id))
        conn.commit()
        conn.close()
        
        return jsonify({'success': True})
        
    except Exception as e:
        print(f"Error updating ad price: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/buy_ad', methods=['POST'])
def buy_ad():
    
    # Получаем данные из запроса
    buy_data = request.get_json()
    if not buy_data:
        return jsonify({'success': False, 'error': 'No data provided'}), 400
        
    ad_id = buy_data.get('ad_id')
    user_id = buy_data.get('user_id')
    
    if not ad_id or not user_id:
        return jsonify({'success': False, 'error': 'Missing ad_id or user_id'}), 400
    
    try:
        # Подключаемся к базе данных
        conn = sqlite3.connect('advert.db')
        cursor = conn.cursor()
        
        # Проверяем, существует ли объявление и активно ли оно
        cursor.execute('''
        SELECT id, user_id FROM advertisements 
        WHERE id = ? AND status = 'active'
        ''', (ad_id,))
        
        ad = cursor.fetchone()
        
        if not ad:
            conn.close()
            return jsonify({'success': False, 'error': 'Объявление не найдено или уже продано'}), 404
        
        seller_id = ad[1]
        
        if seller_id == user_id:
            conn.close()
            return jsonify({'success': False, 'error': 'Нельзя купить собственное объявление'}), 400
        
        # Обновляем статус объявления
        cursor.execute('''
        UPDATE advertisements 
        SET status = 'sold'
        WHERE id = ?
        ''', (ad_id,))
        
        # Здесь можно добавить логику обработки платежа и т.д.
        
        # Сохраняем изменения и закрываем соединение
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': 'Покупка успешно завершена'
        })
        
    except Exception as e:
        print(f"Error processing purchase: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

def parse_webapp_data(init_data):
    """Парсим данные из tgWebAppData"""
    from urllib.parse import parse_qs
    if not init_data:
        return None
    
    parsed = parse_qs(init_data)
    user_data = {}
    
    if 'user' in parsed:
        try:
            import json
            user_json = parsed['user'][0]
            user_data = json.loads(user_json)
            # Добавляем логирование для отладки
            print("Parsed user data:", user_data)
        except Exception as e:
            print("Error parsing user data:", e)
    
    return user_data

@app.route('/save_user', methods=['POST'])
def save_user():
    """Сохраняем/обновляем данные пользователя"""
    try:
        user_data = request.get_json()
        print("Received user data:", user_data)  # Логируем полученные данные
        
        if not user_data or not user_data.get('user_id'):
            return jsonify({'success': False, 'error': 'Invalid request'}), 400
        
        success = check_and_add_user(
            user_id=user_data['user_id'],
            name=user_data.get('name', ''),
            surname=user_data.get('surname', ''),
            username=user_data.get('username', '')
        )
        
        # Проверяем, сохранился ли username
        if success:
            conn = sqlite3.connect('users.db')
            cursor = conn.cursor()
            cursor.execute('SELECT username FROM users WHERE user_id = ?', (str(user_data['user_id']),))
            db_username = cursor.fetchone()
            conn.close()
            print(f"Username in database after save: {db_username}")
        
        return jsonify({'success': success})
    except Exception as e:
        print(f"Error in save_user: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/check_username', methods=['POST'])
def check_username():
    """Проверяем, сохранен ли username в базе"""
    data = request.get_json()
    if not data or not data.get('user_id'):
        return jsonify({'success': False, 'error': 'Invalid request'}), 400
    
    try:
        conn = sqlite3.connect('users.db')
        cursor = conn.cursor()
        cursor.execute('SELECT username FROM users WHERE user_id = ?', (str(data['user_id']),))
        result = cursor.fetchone()
        conn.close()
        
        if result:
            return jsonify({
                'success': True,
                'username': result[0],
                'exists': result[0] is not None
            })
        return jsonify({'success': False, 'error': 'User not found'}), 404
    except Exception as e:
        print(f"Error checking username: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/save_ad', methods=['POST'])
def save_ad():
    
    # Получаем данные из запроса
    ad_data = request.get_json()
    if not ad_data:
        return jsonify({'success': False, 'error': 'No data provided'}), 400
    
    try:
        # Подключаемся к базе данных
        conn = sqlite3.connect('advert.db')
        cursor = conn.cursor()
        
        # Создаем таблицу, если она не существует
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS advertisements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            username TEXT,
            collection TEXT NOT NULL,
            model TEXT NOT NULL,
            number TEXT NOT NULL,
            price REAL NOT NULL,
            currency TEXT NOT NULL,
            created_at TEXT NOT NULL,
            status TEXT DEFAULT 'active'
        )
        ''')
        
        # Use current UTC time if not provided
        created_at = ad_data.get('created_at') or datetime.now(timezone.utc).isoformat()
        
        # Вставляем данные объявления
        cursor.execute('''
        INSERT INTO advertisements 
        (user_id, username, collection, model, number, price, currency, created_at, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            ad_data.get('user_id', ''),
            ad_data.get('username', ''),
            ad_data.get('collection', ''),
            ad_data.get('model', ''),
            ad_data.get('number', ''),
            float(ad_data.get('price', 0)),
            ad_data.get('currency', 'TON'),
            created_at,
            'active'  # Явно устанавливаем статус
        ))
        
        # Сохраняем изменения и закрываем соединение
        conn.commit()
        conn.close()
        
        return jsonify({'success': True})
        
    except Exception as e:
        print(f"Error saving ad to database: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/webapp-data', methods=['POST'])
def webapp_data():
    data = request.json
    if not data:
        return jsonify({"status": "error", "message": "No data provided"}), 400
        
    print("Получены данные от WebApp:", data)
    return jsonify({"status": "success"})

if __name__ == '__main__':
    # Запускаем бота в отдельном потоке
    bot_thread = threading.Thread(target=run_async_task, args=(run_bot,))
    bot_thread.start()
    # Инициализируем базу данных при старте
    init_users_db()
    # Запускаем Flask сервер с отключенной проверкой SSL
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, ssl_context='adhoc')  # Добавлен самоподписанный SSL
    # # Запускаем бота в отдельном потоке
    # bot_thread = threading.Thread(target=run_bot, daemon=True)
    # bot_thread.start()
    
    # # Запускаем Flask сервер
    # port = int(os.environ.get('PORT', 5000))
    # app.run(host='0.0.0.0', port=port)