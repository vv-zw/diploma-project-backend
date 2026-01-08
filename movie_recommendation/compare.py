def compare_algorithms():
    """对比不同推荐算法的效果"""
    from sklearn.metrics import precision_score, recall_score, ndcg_score

    # 测试数据
    test_users = ['user1', 'user2', 'user3']
    metrics = {'precision': [], 'recall': [], 'ndcg': []}

    for user in test_users:
        # 真实喜欢的影片
        true_likes = [b.movie_id for b in Behavior.query.filter_by(openid=user, type='like').all()]

        # 不同算法的推荐结果
        ncf_recs = ncf_recommend(user)
        cf_recs = traditional_cf_recommend(user)
        tfidf_recs = tfidf_based_recommend(user)

        # 计算指标
        for recs in [ncf_recs, cf_recs, tfidf_recs]:
            pred = [1 if movie in recs else 0 for movie in true_likes]
            actual = [1] * len(true_likes)

            precision = precision_score(actual, pred[:len(actual)])
            recall = recall_score(actual, pred[:len(actual)])
            ndcg = ndcg_score([actual], [pred[:len(actual)]])

            metrics['precision'].append(precision)
            metrics['recall'].append(recall)
            metrics['ndcg'].append(ndcg)

    # 输出对比结果
    print("算法对比结果：")
    print(
        f"NCF - 准确率：{np.mean(metrics['precision'][::3]):.2f}, 召回率：{np.mean(metrics['recall'][::3]):.2f}, NDCG：{np.mean(metrics['ndcg'][::3]):.2f}")
    print(
        f"传统CF - 准确率：{np.mean(metrics['precision'][1::3]):.2f}, 召回率：{np.mean(metrics['recall'][1::3]):.2f}, NDCG：{np.mean(metrics['ndcg'][1::3]):.2f}")
    print(
        f"TF-IDF - 准确率：{np.mean(metrics['precision'][2::3]):.2f}, 召回率：{np.mean(metrics['recall'][2::3]):.2f}, NDCG：{np.mean(metrics['ndcg'][2::3]):.2f}")