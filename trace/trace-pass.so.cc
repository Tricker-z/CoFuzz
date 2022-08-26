#define AFL_LLVM_PASS

#include <stdio.h>
#include <stdlib.h>

#include <unordered_map>

#include "include/config.h"
#include "include/debug.h"
#include "llvm/IR/IRBuilder.h"
#include "llvm/IR/LegacyPassManager.h"
#include "llvm/IR/Module.h"
#include "llvm/Support/raw_ostream.h"
#include "llvm/Transforms/IPO/PassManagerBuilder.h"

using namespace llvm;

namespace {

class TracePass : public ModulePass {
 public:
  static char ID;
  std::unordered_map<BasicBlock *, u32> basicBlockMap;

  Type *voidType;
  IntegerType *Int1Ty;
  IntegerType *Int8Ty;
  IntegerType *Int32Ty;
  PointerType *Int8PtrTy;
  PointerType *Int32PtrTy;

  FunctionCallee TraceBranch;
  FunctionCallee TraceSwitch;

  TracePass() : ModulePass(ID) {}

  bool doInitialization(Module &M) override;
  bool runOnModule(Module &M) override;

  std::string getBrCond(Value *condition);

  void visitBranchInst(Module &M, BasicBlock &BB, Instruction *Inst);
  void visitSwitchInst(Module &M, BasicBlock &BB, Instruction *Inst);
};

}  // namespace

char TracePass::ID = 0;

bool TracePass::doInitialization(Module &M) {
  /* Initialize id for each basic block */
  u32 rand_seed;
  char *rand_seed_str = getenv("AFL_RAND_SEED");

  if (rand_seed_str && sscanf(rand_seed_str, "%u", &rand_seed))
    srand(rand_seed);

  for (auto &F : M)
    for (auto &BB : F) {
      u32 cur_loc = AFL_R(MAP_SIZE);
      basicBlockMap.insert(std::pair<BasicBlock *, u32>(&BB, cur_loc));
    }

  return true;
}

inline bool isStrcmp(Value *val) {
  if (CallInst *callInst = dyn_cast<CallInst>(val)) {
    if (Function *func = callInst->getCalledFunction()) {
      std::string called = callInst->getCalledFunction()->getName().str();
      if (called == "strcmp" || called == "strncmp" || called == "memcmp") return true;
    }
  }
  return false;
}

std::string TracePass::getBrCond(Value *condition) {
  /* Condition of the branch instruction */

  if (Instruction *inst = dyn_cast<Instruction>(condition)) {
    switch (inst->getOpcode()) {
      case Instruction::ICmp: {
        ICmpInst *icmpInst = dyn_cast<ICmpInst>(inst);
        Value *oprand0 = icmpInst->getOperand(0);
        Value *oprand1 = icmpInst->getOperand(1);

        std::string icmp_info = "icmp_none";
        if (isStrcmp(oprand0) || isStrcmp(oprand1)) {
          /* strcmp, strncmp, memcmp  */
          icmp_info = "icmp_" + getBrCond(oprand0) + "_" + getBrCond(oprand1);
        } else {
          ICmpInst::Predicate pred = icmpInst->getPredicate();
          icmp_info = "icmp_pred@" + std::to_string(pred);

          if (IntegerType *type = dyn_cast<IntegerType>(oprand0->getType()))
            icmp_info += "_i" + std::to_string(type->getBitWidth());
        }
        return icmp_info;
      }

      case Instruction::FCmp: {
        FCmpInst *fcmpInst = dyn_cast<FCmpInst>(inst);
        FCmpInst::Predicate pred = fcmpInst->getPredicate();
        return "fcmp_pred@" + std::to_string(pred);
      }

      case Instruction::PHI: {
        PHINode *phiNode = dyn_cast<PHINode>(inst);
        std::string phi_info = "phi@";

        for (auto bb_itr = phiNode->block_begin();
             bb_itr != phiNode->block_end(); bb_itr++) {
          if (basicBlockMap.find(*bb_itr) == basicBlockMap.end()) continue;

          phi_info += "(" + std::to_string(basicBlockMap[*bb_itr]) + "," +
                      getBrCond((phiNode->getIncomingValueForBlock(*bb_itr))) +
                      ")";
        }
        return phi_info;
      }

      case Instruction::Call: {
        CallInst *callInst = dyn_cast<CallInst>(inst);
        std::string call_info = "call@";

        if (Function *func = callInst->getCalledFunction())
          call_info += func->getName().str();

        return call_info;
      }

      case Instruction::Or:
        return getBrCond(inst->getOperand(0)) + " || " +
               getBrCond(inst->getOperand(1));

      case Instruction::And:
        return getBrCond(inst->getOperand(0)) + " && " +
               getBrCond(inst->getOperand(1));

      case Instruction::Xor:
        return getBrCond(inst->getOperand(0)) + " ^ " +
               getBrCond(inst->getOperand(1));

      default:
        return "constInst";
    }

  }

  else if (Constant *constVal = dyn_cast<Constant>(condition)) {
    if (constVal->isZeroValue()) return std::to_string(0);
    return std::to_string(1);
  }

  /* Unidentified condition */
  return "none";
}

void TracePass::visitBranchInst(Module &M, BasicBlock &BB, Instruction *Inst) {
  BranchInst *brInst = dyn_cast<BranchInst>(Inst);

  if (brInst->isUnconditional()) return;

  IRBuilder<> IRB(brInst);
  Value *condition = brInst->getCondition();

  std::string cond_info = getBrCond(condition);
  Constant *condConst = ConstantDataArray::getString(M.getContext(), cond_info);

  Value *condInfo = new GlobalVariable(M, condConst->getType(), true,
                                       GlobalValue::PrivateLinkage, condConst);

  IRB.CreateCall(
      TraceBranch,
      {ConstantInt::get(Int32Ty, basicBlockMap[&BB]),
       ConstantInt::get(Int32Ty, basicBlockMap[brInst->getSuccessor(0)]),
       ConstantInt::get(Int32Ty, basicBlockMap[brInst->getSuccessor(1)]),
       condInfo, condition});
}

void TracePass::visitSwitchInst(Module &M, BasicBlock &BB, Instruction *Inst) {
  SwitchInst *switchInst = dyn_cast<SwitchInst>(Inst);
  IRBuilder<> IRB(switchInst);

  u32 case_num = switchInst->getNumCases();
  Value *condition = switchInst->getCondition();

  if (CallInst *inst = dyn_cast<CallInst>(condition)) return;

  u32 bit_width = dyn_cast<IntegerType>(condition->getType())->getBitWidth();

  u32 prev_loc = basicBlockMap[&BB];
  u32 default_loc = basicBlockMap[switchInst->getDefaultDest()];

  AllocaInst *caseCov = IRB.CreateAlloca(ArrayType::get(Int8Ty, case_num));
  AllocaInst *caseLoc = IRB.CreateAlloca(ArrayType::get(Int32Ty, case_num));

  for (auto &caseHandle : switchInst->cases()) {
    ConstantInt *zero = ConstantInt::get(Int32Ty, 0);
    ConstantInt *caseIdx = ConstantInt::get(Int32Ty, caseHandle.getCaseIndex());

    /* Basic block id of the successor */
    u32 succ_idx = caseHandle.getSuccessorIndex();
    BasicBlock *succBB = switchInst->getSuccessor(succ_idx);
    Value *caseLocPtr = IRB.CreateGEP(caseLoc, {zero, caseIdx});
    IRB.CreateStore(ConstantInt::get(Int32Ty, basicBlockMap[succBB]),
                    caseLocPtr);

    /* Case trace state */
    Value *caseCovPtr = IRB.CreateGEP(caseCov, {zero, caseIdx});
    Value *caseTaken = IRB.CreateICmpEQ(condition, caseHandle.getCaseValue());
    IRB.CreateStore(caseTaken, caseCovPtr);
  }

  IRB.CreateCall(TraceSwitch,
                 {ConstantInt::get(Int32Ty, case_num),
                  ConstantInt::get(Int32Ty, bit_width),
                  ConstantInt::get(Int32Ty, prev_loc),
                  ConstantInt::get(Int32Ty, default_loc), caseCov, caseLoc});
}

bool TracePass::runOnModule(Module &M) {
  LLVMContext &C = M.getContext();

  voidType = Type::getVoidTy(C);
  Int1Ty = IntegerType::getInt1Ty(C);
  Int8Ty = IntegerType::getInt8Ty(C);
  Int32Ty = IntegerType::getInt32Ty(C);
  Int8PtrTy = PointerType::get(Int8Ty, 0);
  Int32PtrTy = PointerType::get(Int32Ty, 0);

  /* Log functions to trace the path */
  TraceBranch = (&M)->getOrInsertFunction(
      "__log_branch",
      FunctionType::get(voidType,
                        {Int32Ty, Int32Ty, Int32Ty, Int8PtrTy, Int1Ty}, false));

  TraceSwitch = (&M)->getOrInsertFunction(
      "__log_switch",
      FunctionType::get(
          voidType, {Int32Ty, Int32Ty, Int32Ty, Int32Ty, Int8PtrTy, Int32PtrTy},
          false));

  /* Instrument */
  int inst_blocks = 0;

  for (auto &F : M)
    for (auto &BB : F) {
      Instruction *termInst = BB.getTerminator();

      if (isa<BranchInst>(termInst))
        visitBranchInst(M, BB, termInst);

      else if (isa<SwitchInst>(termInst))
        visitSwitchInst(M, BB, termInst);

      inst_blocks++;
    }

  if (!inst_blocks)
    WARNF("No instrumentation targets found.");
  else
    OKF("Instrumented %u locations", inst_blocks);

  return true;
}

static void registerTracePass(const PassManagerBuilder &,
                              legacy::PassManagerBase &PM) {
  PM.add(new TracePass());
}

static RegisterStandardPasses RegisterMyPass(
    PassManagerBuilder::EP_ModuleOptimizerEarly, registerTracePass);

static RegisterStandardPasses RegisterMyPass0(
    PassManagerBuilder::EP_EnabledOnOptLevel0, registerTracePass);
