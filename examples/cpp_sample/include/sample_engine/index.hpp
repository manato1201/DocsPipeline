#pragma once

#include <string>
#include <vector>

/// 文書検索の小さなエンジン (DocsPipeline の動作確認用サンプル)。
namespace sample_engine {

/// 検索結果の 1 件。
struct Hit {
    std::string id;  ///< 文書の識別子
    double score;    ///< 類似度 (大きいほど近い)
};

/// 文書を登録して、語句で検索する索引。
class Index {
public:
    /**
     * @brief 文書を 1 件登録する。
     * @param id   文書の識別子。すでにあれば置き換える。
     * @param text 本文。
     */
    void add(const std::string& id, const std::string& text);

    /**
     * @brief 語句を含む文書を探す。
     * @param query 検索語。
     * @param limit 返す件数の上限。
     * @return 類似度の高い順の結果。
     */
    std::vector<Hit> search(const std::string& query, std::size_t limit) const;

    /// 登録済みの文書数を返す。
    std::size_t size() const;
};

}  // namespace sample_engine
