"""
API 接口测试

测试所有 API 端点的功能和响应格式。
"""
import pytest
import json
from movie_recommendation.app import app


@pytest.fixture
def client():
    """创建测试客户端"""
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


class TestSystemAPI:
    """系统信息 API 测试"""
    
    def test_index(self, client):
        """测试首页"""
        response = client.get('/')
        assert response.status_code == 200
        assert b'API' in response.data
    
    def test_system_info(self, client):
        """测试系统信息接口"""
        response = client.get('/api/system-info')
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert data['code'] == 0
        assert 'server_time' in data
        assert 'api_version' in data


class TestMovieAPI:
    """电影 API 测试"""
    
    def test_get_movies_data(self, client):
        """测试获取电影数据"""
        response = client.get('/api/movies')
        assert response.status_code in [200, 404]  # 可能数据集不存在
        
        data = json.loads(response.data)
        assert 'code' in data
    
    def test_get_movie_by_name(self, client):
        """测试根据名称查询电影"""
        response = client.post(
            '/api/get-movie-by-name',
            data=json.dumps({'name': '肖申克的救赎'}),
            content_type='application/json'
        )
        assert response.status_code in [200, 404]
        
        data = json.loads(response.data)
        assert 'code' in data
    
    def test_get_movie_by_name_empty(self, client):
        """测试空名称查询"""
        response = client.post(
            '/api/get-movie-by-name',
            data=json.dumps({'name': ''}),
            content_type='application/json'
        )
        assert response.status_code == 400


class TestRecommendationAPI:
    """推荐 API 测试"""
    
    def test_get_recommend(self, client):
        """测试获取推荐"""
        response = client.get('/get_recommend?type=movie')
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert data['code'] == 0
        assert 'data' in data
        assert 'algorithm_version' in data
    
    def test_sync_user_data(self, client):
        """测试同步用户数据"""
        user_data = {
            'preferences': [
                {
                    'id': '1',
                    'name': '测试电影',
                    'genres': ['剧情', '犯罪'],
                    'rating': 9.0
                }
            ]
        }
        
        response = client.post(
            '/sync-user-data',
            data=json.dumps(user_data),
            content_type='application/json'
        )
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert data['code'] == 0
        assert 'count_weights' in data


class TestSearchAPI:
    """搜索 API 测试"""
    
    def test_search(self, client):
        """测试搜索功能"""
        response = client.get('/search?q=肖申克')
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert data['code'] == 0
        assert 'results' in data
    
    def test_search_empty_query(self, client):
        """测试空查询"""
        response = client.get('/search?q=')
        assert response.status_code == 400


class TestWatchlistAPI:
    """想看清单 API 测试"""
    
    def test_get_watchlist(self, client):
        """测试获取想看清单"""
        response = client.get('/watchlist')
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert data['code'] == 0
        assert 'watchlist' in data
    
    def test_add_to_watchlist(self, client):
        """测试添加到想看清单"""
        item_data = {
            'item_id': 'test_1',
            'type': 'movie',
            'data': {
                'title': '测试电影',
                'rating': '9.0'
            }
        }
        
        response = client.post(
            '/watchlist/add',
            data=json.dumps(item_data),
            content_type='application/json'
        )
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert data['code'] == 0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
