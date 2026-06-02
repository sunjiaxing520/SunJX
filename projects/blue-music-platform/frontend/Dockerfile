FROM node:18-alpine

WORKDIR /app

# 复制 package.json 和 package-lock.json
COPY package*.json ./

# 安装依赖
RUN npm install

# 复制源码
COPY . .

# 启动开发服务器
CMD ["npm", "start"]
