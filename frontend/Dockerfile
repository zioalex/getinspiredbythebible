FROM node:25-alpine

WORKDIR /app

# Install dependencies
COPY package*.json ./
RUN npm install

# Copy source
COPY . .

# Development mode
EXPOSE 3000

CMD ["npm", "run", "dev"]
