# 上传到 GitHub

## 1. 在 GitHub 创建空仓库

打开 https://github.com/new，建议填写：

- Repository name：`parcel-vision-api`
- Visibility：`Private`
- 不勾选 README、`.gitignore` 和 License

点击 `Create repository`。

## 2. 提交本地项目

```bash
cd "/Users/lixing.guo/Documents/机械臂/parcel-vision-api"
git add .
git commit -m "Initial parcel vision API"
```

## 3. 绑定 GitHub 仓库

把 `<GitHub用户名>` 替换成实际用户名：

```bash
git remote add origin https://github.com/<GitHub用户名>/parcel-vision-api.git
git push -u origin main
```

GitHub 不接受账号密码进行 Git 推送。出现登录提示时，使用浏览器授权或 Personal Access Token。

## 4. 后续更新

```bash
git add .
git commit -m "Describe the change"
git push
```

## 大文件说明

项目已通过 `.gitignore` 排除 `data/` 和 `reports/`。大型现场点云、视频和模型权重不要直接提交到普通 Git；可以使用 Git LFS、GitHub Release 或对象存储。
