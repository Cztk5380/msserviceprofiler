
#include <gtest/gtest.h>
#include <mockcpp/mockcpp.hpp>


int multi(int a, int b) {
    return a * b;
}

TEST(TestMock, TestMock) {
    MOCKER(multi).stubs().will(returnValue(100000));

    EXPECT_EQ(100000, multi(1, 2));
}